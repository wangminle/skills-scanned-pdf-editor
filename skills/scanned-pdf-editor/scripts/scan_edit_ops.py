#!/usr/bin/env python3
"""扫描版 PDF / 图片局部编辑的统一 CLI。

子命令一览（export-page 为 extract 的兼容旧名）：
  remove       - 删除指定区域（墨迹蒙版 + Telea 修补 / 行间插值填底）
  move         - 移动原生像素块并清理残留
  replace      - 原生供体替换
  compound     - 复合操作：复制源块 → 清除多个区域 → 粘贴到新位置
  verify       - 像素级验证
  package      - 结果图封装为 PDF（新建页，或替换内嵌图、保留 OCR 层）
  extract      - 安全提取 PDF 页内嵌整页图并默认做往返封装验证

坐标统一使用页面 PNG 的左上角像素坐标，矩形 (x1,y1,x2,y2) 右下不包含。

用法示例:
  # 删除
  python3 scan_edit_ops.py remove --source page.png \\
      --boxes "1197,1665,1288,1718" --output page_removed.png

  # 移动
  python3 scan_edit_ops.py move --source page.png \\
      --content-x 330,2250 --source-y 1735,3070 --shift-y 265 \\
      --output page_moved.png

  # 替换
  python3 scan_edit_ops.py replace --source page.png \\
      --donor-source donor.png --donor-box 787,945,877,997 \\
      --remove-boxes "1195,585,1285,637" --destination 1195,585 \\
      --reference-box 651,585,696,638 --output page_replaced.png

  # 验证
  python3 scan_edit_ops.py verify --source page.png --result page_edited.png \\
      --allowed-boxes "330,1470,2250,3062"
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import scan_edit_utils as utils


def parse_box(s: str) -> utils.Box:
    parts = s.replace(" ", "").split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"坐标格式应为 x1,y1,x2,y2，收到: {s}")
    box = tuple(int(p) for p in parts)
    x1, y1, x2, y2 = box
    # BUG-037：负坐标会被 numpy 当成"从末尾倒数"的负索引，把操作静默移到错误区域
    # （如 x1=-50 实际覆盖第 50..倒数第 50 列），全程无报错。像素坐标必须非负。
    if x1 < 0 or y1 < 0 or x2 < 0 or y2 < 0:
        raise argparse.ArgumentTypeError(
            f"坐标需全部非负（像素坐标），收到: {s}（解析为 {box}）。"
            "请检查是否误用了负值或计算溢出。"
        )
    # BUG-028：倒置框（x2<x1 或 y2<y1）静默接受后产生空切片，删除等操作无效果。
    if x1 >= x2 or y1 >= y2:
        raise argparse.ArgumentTypeError(
            f"坐标需满足 x1<x2 且 y1<y2，收到: {s}（解析为 {box}）。"
            "请检查是否写反了起止点或输入了空框。"
        )
    return box


def parse_boxes(s: str) -> list[utils.Box]:
    return [parse_box(b) for b in s.split(";")]


def parse_pair(s: str) -> tuple[int, int]:
    """解析点坐标或无序二元组（如 --destination x,y）。不强制 a<b。"""
    parts = s.replace(" ", "").split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"格式应为 a,b，收到: {s}")
    return tuple(int(p) for p in parts)


def parse_ordered_pair(s: str) -> tuple[int, int]:
    """解析有序区间 a,b，要求 a<b（如 --content-x / --source-y）。

    BUG-033：倒置/零宽区间若仅靠库函数兜底，CLI 仍会先跑到半截；与 parse_box 对齐。
    """
    pair = parse_pair(s)
    a, b = pair
    if a >= b:
        raise argparse.ArgumentTypeError(
            f"区间需满足 a<b，收到: {s}（解析为 {pair}）。"
            "请检查是否写反了起止点。"
        )
    return pair


def parse_thresholds(s: str) -> tuple[int, ...]:
    """解析逗号分隔的亮度阈值并去重保序。"""
    try:
        values = tuple(dict.fromkeys(int(part.strip()) for part in s.split(",") if part.strip()))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"阈值须为逗号分隔整数，收到: {s!r}") from exc
    if not values or any(value < 1 or value > 255 for value in values):
        raise argparse.ArgumentTypeError(f"阈值须位于 1..255，收到: {s!r}")
    return values


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def save_with_preview(
    image: np.ndarray,
    output: Path,
    crop_box: utils.Box | None = None,
) -> None:
    """保存全页图，可选附一张裁剪预览。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    pil = Image.fromarray(image)
    pil.save(output, dpi=(300, 300))
    if crop_box:
        preview = output.with_name(output.stem + "_crop.png")
        pil.crop(crop_box).save(preview)
        print(f"preview: {preview}")
    print(f"saved: {output}")


def make_location_image(source: np.ndarray, boxes, labels=None) -> Image.Image:
    """在源图上画框，生成定位标注图。"""
    pil = Image.fromarray(source).copy()
    draw = ImageDraw.Draw(pil)
    colors = [(230, 35, 35), (35, 95, 230), (30, 165, 80), (165, 30, 165)]
    for i, box in enumerate(boxes):
        color = colors[i % len(colors)]
        draw.rectangle(box, outline=color, width=8)
    return pil


# ───────────────────────────── remove ─────────────────────────────


def cmd_remove(args: argparse.Namespace) -> int:
    source = load_rgb(args.source)
    boxes = [parse_box(b) for b in args.boxes]

    if args.method == "telea":
        result, mask = utils.remove_regions_telea(
            source,
            boxes,
            ink_threshold=args.ink_threshold,
            dilation=args.dilation,
            inpaint_radius=args.inpaint_radius,
            mask_mode=args.mask_mode,
        )
        if args.save_mask:
            Image.fromarray(mask).save(args.save_mask)
            print(f"mask: {args.save_mask}")
    else:
        result = utils.remove_regions_interpolate(
            source, boxes, noise_sigma=args.noise_sigma, seed=args.seed
        )
        if args.save_mask:
            print(
                "注意: interpolate 方法不产生蒙版，--save-mask 仅对 telea 生效，已忽略。",
                file=sys.stderr,
            )

    save_with_preview(result, args.output, args.crop_box)

    # 定位图
    if args.save_location:
        make_location_image(source, boxes).save(args.save_location)
        print(f"location: {args.save_location}")

    # 差分统计
    diff = utils.image_diff(source, result)
    print(f"changed_pixels={diff.changed_pixels}")
    if diff.bbox:
        print(f"changed_bbox={diff.bbox}")
    return 0


# ───────────────────────────── move ─────────────────────────────


def cmd_move(args: argparse.Namespace) -> int:
    source = load_rgb(args.source)
    content_x = parse_ordered_pair(args.content_x)
    source_y = parse_ordered_pair(args.source_y)
    shift_y = args.shift_y

    cleanup_boxes = None
    if args.cleanup_boxes:
        cleanup_boxes = [parse_box(b) for b in args.cleanup_boxes]

    result, mask = utils.move_block(
        source,
        content_x=content_x,
        source_y=source_y,
        shift_y=shift_y,
        cleanup_boxes=cleanup_boxes,
        cleanup_mode=args.cleanup_mode,
        cleanup_ink_threshold=args.cleanup_ink_threshold,
    )

    save_with_preview(result, args.output, args.crop_box)

    if args.save_mask:
        Image.fromarray(mask).save(args.save_mask)
        print(f"mask: {args.save_mask}")

    diff = utils.image_diff(source, result)
    print(f"shift_y={shift_y}")
    print(f"changed_pixels={diff.changed_pixels}")
    if diff.bbox:
        print(f"changed_bbox={diff.bbox}")
    return 0


# ───────────────────────────── replace ─────────────────────────────


def cmd_replace(args: argparse.Namespace) -> int:
    source = load_rgb(args.source)
    donor_source = load_rgb(args.donor_source) if args.donor_source else source
    donor_box = parse_box(args.donor_box)
    remove_boxes = [parse_box(b) for b in args.remove_boxes]
    destination = parse_pair(args.destination)
    reference_box = parse_box(args.reference_box)

    erased, _ = utils.remove_regions_telea(
        source,
        remove_boxes,
        ink_threshold=args.ink_threshold,
        mask_mode=args.mask_mode,
    )
    result, mask, scale = utils.replace_with_donor(
        source,
        donor_source,
        donor_box=donor_box,
        remove_boxes=remove_boxes,
        destination=destination,
        reference_box=reference_box,
        feather=args.feather,
        ink_threshold=args.ink_threshold,
        mask_mode=args.mask_mode,
        normalize_mode=args.normalize_mode,
    )

    save_with_preview(result, args.output, args.crop_box)

    if args.save_mask:
        Image.fromarray(mask).save(args.save_mask)
        print(f"mask: {args.save_mask}")

    diff = utils.image_diff(source, result)
    print(f"contrast_scale={scale:.4f}")
    print(f"changed_pixels={diff.changed_pixels}")
    if diff.bbox:
        print(f"changed_bbox={diff.bbox}")

    donor_w = donor_box[2] - donor_box[0]
    donor_h = donor_box[3] - donor_box[1]
    placement = utils.analyze_replace_placement(
        erased,
        result,
        destination_box=(
            destination[0], destination[1],
            destination[0] + donor_w, destination[1] + donor_h,
        ),
        reference_box=reference_box,
        threshold=args.analysis_threshold,
    )
    print("placement_analysis=" + json.dumps({
        "threshold": args.analysis_threshold,
        "inserted_ink_bbox": placement.inserted_ink_bbox,
        "collision_pixels": placement.collision_pixels,
        "nearest_gap_px": placement.nearest_gap_px,
        "left_gap_px": placement.left_gap_px,
        "right_gap_px": placement.right_gap_px,
        "baseline_delta_px": placement.baseline_delta_px,
        "center_delta_px": placement.center_delta_px,
    }, ensure_ascii=False))
    if args.fail_on_collision and placement.collision_pixels:
        print(f"错误: 供体与保留墨迹相交 {placement.collision_pixels} 像素", file=sys.stderr)
        return 1
    if args.min_gap is not None and (
        placement.nearest_gap_px is None or placement.nearest_gap_px < args.min_gap
    ):
        print(
            f"错误: 最近墨迹距离 {placement.nearest_gap_px} 小于要求 {args.min_gap}",
            file=sys.stderr,
        )
        return 1
    if args.max_baseline_deviation is not None and (
        placement.baseline_delta_px is None
        or abs(placement.baseline_delta_px) > args.max_baseline_deviation
    ):
        print(
            f"错误: 基线偏差 {placement.baseline_delta_px} 超过 ±{args.max_baseline_deviation}px",
            file=sys.stderr,
        )
        return 1
    return 0


# ───────────────────────────── verify ─────────────────────────────


def cmd_compound(args: argparse.Namespace) -> int:
    """复合操作：复制源块 -> 清除多个区域 -> 粘贴源块到新位置。

    适用于 task007 类"先复制再清除"的复合流程（G6）。
    """
    source = load_rgb(args.source)
    content_x = parse_ordered_pair(args.content_x)
    source_y = parse_ordered_pair(args.source_y)
    clear_boxes = [parse_box(b) for b in args.clear_boxes]

    result = utils.move_and_clear(
        source,
        content_x=content_x,
        source_y=source_y,
        shift_y=args.shift_y,
        clear_boxes=clear_boxes,
        noise_sigma=args.noise_sigma,
        seed=args.seed,
    )

    save_with_preview(result, args.output, args.crop_box)

    diff = utils.image_diff(source, result)
    print(f"shift_y={args.shift_y}")
    print(f"changed_pixels={diff.changed_pixels}")
    if diff.bbox:
        print(f"changed_bbox={diff.bbox}")
    return 0


# ───────────────────────────── verify ─────────────────────────────


def cmd_verify(args: argparse.Namespace) -> int:
    source = load_rgb(args.source)
    result = load_rgb(args.result)

    if source.shape != result.shape:
        print(f"错误: 尺寸不一致 {source.shape} != {result.shape}", file=sys.stderr)
        return 1

    diff = utils.image_diff(source, result)
    print(f"changed_pixels={diff.changed_pixels}")
    if diff.bbox:
        print(f"changed_bbox={diff.bbox}")

    if args.allowed_boxes:
        allowed = [parse_box(b) for b in args.allowed_boxes]
        outside = utils.changes_outside_boxes(source, result, allowed)
        print(f"outside_allowed={outside}")
        if outside > 0:
            print(f"错误: 允许区域外有 {outside} 个变化像素", file=sys.stderr)
            return 1

    if args.blank_box:
        box = parse_box(args.blank_box)
        # BUG-039：框完全越界时切片为空，dark=0 被误读为"验证通过"。
        # 框必须与图像有交集，否则没有检查任何像素，验证结论无效。
        bx1, by1, bx2, by2 = box
        rh, rw = result.shape[:2]
        ix1, iy1 = max(0, bx1), max(0, by1)
        ix2, iy2 = min(rw, bx2), min(rh, by2)
        if ix1 >= ix2 or iy1 >= iy2:
            print(
                f"错误: --blank-box {box} 与图像 {rw}×{rh} 没有交集，"
                "验证未覆盖任何像素。",
                file=sys.stderr,
            )
            return 1
        limit = args.blank_limit if args.blank_limit is not None else 0
        thresholds = args.blank_thresholds
        for threshold in thresholds:
            dark = utils.blank_region_dark_pixels(result, box, threshold=threshold)
            print(f"blank_dark_pixels={dark} (threshold<{threshold})")
            if dark > limit:
                print(
                    f"错误: 空白区亮度<{threshold} 的像素 {dark} 超过上限 {limit}",
                    file=sys.stderr,
                )
                return 1

    if args.preserve_box:
        box = parse_box(args.preserve_box)
        # BUG-039：与 blank-box 同理，完全越界的 preserve-box 会得到空切片、
        # preserved=0 被误读为"应保留区域无变化"。
        px1, py1, px2, py2 = box
        rh, rw = result.shape[:2]
        ix1, iy1 = max(0, px1), max(0, py1)
        ix2, iy2 = min(rw, px2), min(rh, py2)
        if ix1 >= ix2 or iy1 >= iy2:
            print(
                f"错误: --preserve-box {box} 与图像 {rw}×{rh} 没有交集，"
                "验证未覆盖任何像素。",
                file=sys.stderr,
            )
            return 1
        preserved = int(np.count_nonzero(
            np.any(source[py1:py2, px1:px2] != result[py1:py2, px1:px2], axis=2)
        ))
        print(f"preserve_region_changes={preserved}")
        if preserved > 0:
            print(f"错误: 应保留区域有 {preserved} 个变化像素", file=sys.stderr)
            return 1

    print("验证通过。")
    return 0




# ───────────────────────────── package ─────────────────────────────


def cmd_package(args: argparse.Namespace) -> int:
    """将编辑后的图片封装为 PDF。

    两种模式：
    - --original-pdf 给出时：用 PyMuPDF replace_image 替换内嵌图，保留 OCR 文字层；
      若编辑图是阅读器显示朝向（与 /Rotate 后尺寸一致），自动旋回内嵌朝向再替换。
    - 不给 --original-pdf 时：用 PyMuPDF 按指定页面尺寸新建单页 PDF
    """
    from PIL import Image as PILImage
    image = PILImage.open(args.source).convert("RGB")

    if args.original_pdf:
        meta = utils.extract_embedded_page_image(
            Path(args.original_pdf),
            page_index=args.page_index,
            as_displayed=False,
        )
        try:
            before = image.size
            image = utils.prepare_image_for_pdf_replace(
                image,
                embedded_size=meta.embedded_size,
                displayed_size=meta.displayed_size,
                rotate=meta.rotate,
                source_orient=args.source_orient,
            )
        except ValueError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            return 2
        if before != image.size:
            print(
                f"package: 已按 /Rotate={meta.rotate} 将显示朝向 "
                f"{before[0]}×{before[1]} 旋回内嵌朝向 "
                f"{image.width}×{image.height}"
            )
        allowed_boxes = [parse_box(box) for box in (args.audit_allowed_boxes or [])]
        if not args.skip_render_audit and not allowed_boxes:
            print(
                "错误: 保留原 PDF 封装默认启用 300dpi 区外变化门禁，"
                "必须用 --audit-allowed-boxes 声明允许修改区；"
                "仅在明确不需要像素审计时使用 --skip-render-audit。",
                file=sys.stderr,
            )
            return 2

        args.output.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            suffix=".pdf", prefix=".scan-package-", dir=args.output.parent, delete=False
        )
        handle.close()
        candidate = Path(handle.name)
        candidate.unlink(missing_ok=True)
        try:
            utils.replace_pdf_image(
                Path(args.original_pdf), candidate, image,
                page_index=args.page_index,
            )

            # 门禁 1：回读成品内嵌图，必须与准备封装的 RGB 像素逐像素一致。
            back = utils.extract_embedded_page_image(
                candidate, page_index=args.page_index, as_displayed=False
            )
            if not np.array_equal(
                np.asarray(back.image.convert("RGB")), np.asarray(image.convert("RGB"))
            ):
                print("错误: 封装后内嵌图与编辑图像素不一致，拒绝交付。", file=sys.stderr)
                return 1
            print("embedded_roundtrip_diff=0")

            # 门禁 2：所有未修改页的原生扫描图像素哈希必须保持一致。
            mismatches = utils.compare_unmodified_page_hashes(
                Path(args.original_pdf), candidate, modified_pages={args.page_index}
            )
            if mismatches:
                pages = ", ".join(str(index + 1) for index in mismatches)
                print(f"错误: 未修改页面内嵌图哈希变化: 第 {pages} 页", file=sys.stderr)
                return 1
            print(f"unmodified_page_hashes=ok ({max(0, utils.pdf_page_info(candidate)[0] - 1)} pages)")

            # 门禁 3：同一渲染器 300dpi 回渲，声明区域外变化必须为 0。
            if not args.skip_render_audit:
                audit = utils.audit_pdf_render_outside_boxes(
                    Path(args.original_pdf),
                    candidate,
                    page_index=args.page_index,
                    allowed_boxes=allowed_boxes,
                    boxes_size=meta.displayed_size,
                    dpi=args.audit_dpi,
                    padding=args.audit_padding,
                )
                print(
                    f"render_audit_{args.audit_dpi}dpi: changed={audit.changed_pixels}, "
                    f"bbox={audit.changed_bbox}, outside_allowed={audit.outside_allowed}"
                )
                if audit.outside_allowed:
                    print(
                        f"错误: {args.audit_dpi}dpi 回渲在允许区外出现 "
                        f"{audit.outside_allowed} 个变化像素，拒绝交付。",
                        file=sys.stderr,
                    )
                    return 1

            candidate.replace(args.output)
        finally:
            candidate.unlink(missing_ok=True)
    else:
        if args.page_size:
            # BUG-024：数值个数不对或非数字时，原先裸抛 IndexError/ValueError。
            parts = args.page_size.replace(" ", "").split(",")
            try:
                if len(parts) != 2:
                    raise ValueError
                page_w, page_h = float(parts[0]), float(parts[1])
                if not (np.isfinite(page_w) and np.isfinite(page_h)):
                    raise ValueError
                if page_w <= 0 or page_h <= 0:
                    raise ValueError
                page_size = (page_w, page_h)
            except ValueError:
                print(
                    f"错误: --page-size 需要 W,H 两个数值（如 595.2,841.68），"
                    f"收到: {args.page_size!r}",
                    file=sys.stderr,
                )
                return 2
        else:
            # 按图像尺寸和 dpi 推算页面点尺寸
            # BUG-035：dpi<=0 会 ZeroDivisionError / 负 page_size 裸崩，与 --page-size 同样给 exit 2。
            dpi = args.dpi
            if dpi is None or dpi <= 0:
                print(
                    f"错误: --dpi 需为正整数（用于从图像推算页面尺寸），收到: {args.dpi!r}",
                    file=sys.stderr,
                )
                return 2
            page_size = (image.width * 72.0 / dpi, image.height * 72.0 / dpi)
        utils.save_image_as_pdf(
            image, args.output,
            page_size=page_size,
            title=args.title or "",
            subject=args.subject or "",
        )

    print(f"saved: {args.output}")
    return 0


def cmd_export_page(args: argparse.Namespace) -> int:
    """安全提取 PDF 页内嵌整页扫描图，并可做往返封装验证。"""
    try:
        meta = utils.extract_embedded_page_image(
            Path(args.pdf),
            page_index=args.page_index,
            as_displayed=args.as_displayed,
        )
    except (IndexError, RuntimeError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    meta.image.save(args.output)
    orient = "displayed" if args.as_displayed else "embedded"
    print(
        f"saved: {args.output}  ({meta.image.width}×{meta.image.height}, "
        f"orient={orient}, /Rotate={meta.rotate}, "
        f"embedded={meta.embedded_size[0]}×{meta.embedded_size[1]}, "
        f"displayed={meta.displayed_size[0]}×{meta.displayed_size[1]})"
    )
    # PNG 自身回读必须逐像素一致，防止输出链发生颜色空间或调色板转换。
    saved = np.asarray(Image.open(args.output).convert("RGB"))
    expected = np.asarray(meta.image.convert("RGB"))
    if not np.array_equal(saved, expected):
        print("错误: 提取图保存后像素发生变化。", file=sys.stderr)
        args.output.unlink(missing_ok=True)
        return 1

    if not args.no_roundtrip_check:
        handle = tempfile.NamedTemporaryFile(suffix=".pdf", prefix="scan-extract-check-", delete=False)
        handle.close()
        candidate = Path(handle.name)
        candidate.unlink(missing_ok=True)
        try:
            embedded = utils.prepare_image_for_pdf_replace(
                meta.image,
                embedded_size=meta.embedded_size,
                displayed_size=meta.displayed_size,
                rotate=meta.rotate,
                source_orient="displayed" if args.as_displayed else "embedded",
            )
            utils.replace_pdf_image(Path(args.pdf), candidate, embedded, page_index=args.page_index)
            back = utils.extract_embedded_page_image(candidate, page_index=args.page_index)
            embedded_equal = np.array_equal(
                np.asarray(back.image.convert("RGB")), np.asarray(embedded.convert("RGB"))
            )
            before = np.asarray(utils.render_pdf_page_mupdf(
                Path(args.pdf), page_index=args.page_index, dpi=args.audit_dpi
            ))
            after = np.asarray(utils.render_pdf_page_mupdf(
                candidate, page_index=args.page_index, dpi=args.audit_dpi
            ))
            render_equal = before.shape == after.shape and np.array_equal(before, after)
            unchanged = utils.compare_unmodified_page_hashes(
                Path(args.pdf), candidate, modified_pages={args.page_index}
            )
            print("roundtrip_check=" + json.dumps({
                "embedded_diff_pixels": int(np.count_nonzero(np.any(
                    np.asarray(back.image.convert("RGB")) != np.asarray(embedded.convert("RGB")), axis=2
                ))) if embedded_equal is False else 0,
                "render_dpi": args.audit_dpi,
                "render_backend": "pymupdf",
                "render_equal": render_equal,
                "unmodified_page_hashes_equal": not unchanged,
            }, ensure_ascii=False))
            if not embedded_equal or not render_equal or unchanged:
                print("错误: 提取图往返封装验证失败，拒绝将其作为编辑基图。", file=sys.stderr)
                args.output.unlink(missing_ok=True)
                return 1
        finally:
            candidate.unlink(missing_ok=True)
    return 0


# ───────────────────────────── CLI ─────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="扫描版 PDF / 图片局部编辑：删除、移动、替换、复合、验证、封装 PDF、安全提取（export-page 为兼容旧名）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # remove
    pr = sub.add_parser("remove", help="删除指定区域")
    pr.add_argument("--source", type=Path, required=True, help="源图片路径")
    pr.add_argument("--boxes", nargs="+", required=True, help="删除区域 x1,y1,x2,y2（可多个）")
    pr.add_argument("--method", choices=["telea", "interpolate"], default="telea",
                    help="删除方法（默认 telea）")
    pr.add_argument("--ink-threshold", type=int, default=180, help="墨迹亮度阈值（默认 180）")
    pr.add_argument("--dilation", type=int, default=5, help="膨胀核大小（默认 5）")
    pr.add_argument("--inpaint-radius", type=int, default=5, help="修补半径（默认 5）")
    pr.add_argument("--mask-mode", choices=["ink", "full"], default="ink",
                    help="蒙版模式：ink=只清理墨迹（默认），full=整矩形清理（G2）")
    pr.add_argument("--noise-sigma", type=float, default=0.45, help="插值法噪点标准差（默认 0.45）")
    pr.add_argument("--seed", type=int, default=20260805, help="随机种子")
    pr.add_argument("--output", type=Path, required=True, help="输出路径")
    pr.add_argument("--crop-box", type=parse_box, help="预览裁剪框")
    pr.add_argument("--save-mask", type=Path, help="保存清理蒙版")
    pr.add_argument("--save-location", type=Path, help="保存定位标注图")
    pr.set_defaults(func=cmd_remove)

    # move
    pm = sub.add_parser("move", help="移动像素块并清理残留")
    pm.add_argument("--source", type=Path, required=True, help="源图片路径")
    pm.add_argument("--content-x", required=True, help="横向范围 x1,x2（须 x1<x2）")
    pm.add_argument("--source-y", required=True, help="纵向范围 y1,y2（须 y1<y2）")
    pm.add_argument("--shift-y", type=int, required=True, help="上移像素数（正值=上移）")
    pm.add_argument("--cleanup-ink-threshold", type=int, default=246, help="残留清理墨迹阈值（默认 246）")
    pm.add_argument(
        "--cleanup-mode", choices=["auto", "add", "replace"], default="auto",
        help="清理框语义：auto=仅自动尾部框（默认）；add=自动框+手动框；replace=仅手动框",
    )
    pm.add_argument(
        "--cleanup-boxes", nargs="+",
        help="手动清理区域；须配合 --cleanup-mode add 或 replace",
    )
    pm.add_argument("--output", type=Path, required=True, help="输出路径")
    pm.add_argument("--crop-box", type=parse_box, help="预览裁剪框")
    pm.add_argument("--save-mask", type=Path, help="保存清理蒙版")
    pm.set_defaults(func=cmd_move)

    # replace
    pe = sub.add_parser("replace", help="原生供体替换")
    pe.add_argument("--source", type=Path, required=True, help="目标图片路径")
    pe.add_argument("--donor-source", type=Path, help="供体图片路径（不给则与 source 相同）")
    pe.add_argument("--donor-box", required=True, help="供体词块框 x1,y1,x2,y2")
    pe.add_argument("--remove-boxes", nargs="+", required=True, help="目标清理框（可多个）")
    pe.add_argument("--destination", required=True, help="贴入左上角 x,y")
    pe.add_argument("--reference-box", required=True, help="目标行参考字框 x1,y1,x2,y2")
    pe.add_argument("--feather", type=int, default=4, help="羽化宽度（默认 4；<=0 为硬边）")
    pe.add_argument("--ink-threshold", type=int, default=180, help="清理墨迹阈值（默认 180）")
    pe.add_argument("--mask-mode", choices=["ink", "full"], default="ink",
                    help="清理蒙版模式：ink=墨迹蒙版（默认），full=整矩形蒙版（G2）")
    pe.add_argument("--normalize-mode", choices=["contrast", "offset"], default="contrast",
                    help="供体归一化模式：contrast=对比度缩放（默认），offset=纯底色偏移（G3）")
    pe.add_argument("--output", type=Path, required=True, help="输出路径")
    pe.add_argument("--crop-box", type=parse_box, help="预览裁剪框")
    pe.add_argument("--save-mask", type=Path, help="保存清理蒙版")
    pe.add_argument("--analysis-threshold", type=int, default=220,
                    help="碰撞/字距/基线分析的墨迹阈值（默认 220）")
    pe.add_argument("--fail-on-collision", action="store_true",
                    help="供体与清理后保留墨迹相交时失败")
    pe.add_argument("--min-gap", type=float,
                    help="最近墨迹距离下限（像素；不足则失败）")
    pe.add_argument("--max-baseline-deviation", type=int,
                    help="相对参考字的最大基线偏差绝对值（像素）")
    pe.set_defaults(func=cmd_replace)

    # compound
    pc = sub.add_parser("compound", help="复合操作：复制源块→清除多个区域→粘贴源块到新位置")
    pc.add_argument("--source", type=Path, required=True, help="源图片路径")
    pc.add_argument("--content-x", required=True, help="移动区域横向范围 x1,x2（须 x1<x2）")
    pc.add_argument("--source-y", required=True, help="移动区域纵向范围 y1,y2（须 y1<y2）")
    pc.add_argument("--shift-y", type=int, required=True, help="上移像素数（正值=上移）")
    pc.add_argument("--clear-boxes", nargs="+", required=True,
                    help="需清除的所有区域 x1,y1,x2,y2（可多个，通常含源区域本身）")
    pc.add_argument("--noise-sigma", type=float, default=0.45, help="插值法噪点标准差（默认 0.45）")
    pc.add_argument("--seed", type=int, default=20260805, help="随机种子")
    pc.add_argument("--output", type=Path, required=True, help="输出路径")
    pc.add_argument("--crop-box", type=parse_box, help="预览裁剪框")
    pc.set_defaults(func=cmd_compound)

    # verify
    pv = sub.add_parser("verify", help="像素级验证")
    pv.add_argument("--source", type=Path, required=True, help="原图路径")
    pv.add_argument("--result", type=Path, required=True, help="编辑后图路径")
    pv.add_argument("--allowed-boxes", nargs="+", help="允许变化的区域（可多个）")
    pv.add_argument("--blank-box", help="空白检查区域 x1,y1,x2,y2")
    pv.add_argument(
        "--blank-thresholds", type=parse_thresholds, default=(180, 220, 240),
        help="空白区残影检查阈值，逗号分隔（默认 180,220,240）",
    )
    pv.add_argument(
        "--blank-threshold", dest="blank_thresholds",
        type=lambda value: parse_thresholds(value), default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    pv.add_argument("--blank-limit", type=int, help="空白区深色像素上限（默认 0）")
    pv.add_argument("--preserve-box", help="应保留不变的区域 x1,y1,x2,y2")
    pv.set_defaults(func=cmd_verify)


    # package
    pp = sub.add_parser("package", help="将编辑后的图片封装为 PDF")
    pp.add_argument("--source", type=Path, required=True, help="编辑后的图片路径")
    pp.add_argument("--output", type=Path, required=True, help="输出 PDF 路径")
    pp.add_argument("--original-pdf", type=Path,
                    help="原始 PDF 路径（给出则用 replace_image 保留 OCR 层；不给则新建 PDF）")
    pp.add_argument("--page-size", help="页面点尺寸 W,H（两个正数；不给则按 --dpi 从图像推算）")
    pp.add_argument("--dpi", type=int, default=300, help="推算页面尺寸用的 dpi（须为正整数，默认 300）")
    pp.add_argument("--page-index", type=int, default=0, help="替换内嵌图的页码（默认 0）")
    pp.add_argument(
        "--source-orient", choices=["auto", "embedded", "displayed"], default="auto",
        help="输入图朝向：auto=按尺寸推断（默认）；displayed=extract --as-displayed "
             "导出的显示朝向图（编辑后回封，/Rotate≠0 时旋回）；embedded=内嵌朝向图。"
             "/Rotate=180 或正方形图尺寸无法区分朝向，必须显式指定（BUG-066）。",
    )
    pp.add_argument("--title", help="PDF 标题元数据")
    pp.add_argument("--subject", help="PDF 主题元数据")
    pp.add_argument(
        "--audit-allowed-boxes", nargs="+",
        help="允许修改区（显示朝向提取图坐标，可多个）；保留原 PDF 封装时默认必填",
    )
    pp.add_argument("--audit-dpi", type=int, default=300,
                    help="封装回渲审计 dpi（默认 300）")
    pp.add_argument("--audit-padding", type=int, default=2,
                    help="允许框映射到回渲图后的边界扩展像素（默认 2）")
    pp.add_argument("--skip-render-audit", action="store_true",
                    help="显式跳过区外回渲门禁；内嵌图往返与未修改页哈希仍强制检查")
    pp.set_defaults(func=cmd_package)

    # extract：安全提取；export-page 保留为兼容别名。
    for command, help_text in (
        ("extract", "安全提取 PDF 页内嵌整页图，并默认验证往返封装像素"),
        ("export-page", "兼容旧名：等同 extract"),
    ):
        px = sub.add_parser(command, help=help_text)
        px.add_argument("--pdf", type=Path, required=True, help="源 PDF 路径")
        px.add_argument("--output", type=Path, required=True, help="输出 PNG 路径")
        px.add_argument("--page-index", type=int, default=0, help="页码（默认 0）")
        px.add_argument(
            "--as-displayed", action="store_true",
            help="按 /Rotate 转到阅读器显示朝向",
        )
        px.add_argument("--audit-dpi", type=int, default=300,
                        help="往返封装回渲检查 dpi（默认 300）")
        px.add_argument("--no-roundtrip-check", action="store_true",
                        help="跳过提取后的往返封装验证（不推荐）")
        px.set_defaults(func=cmd_export_page)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # BUG-046：多框参数（--boxes / --cleanup-boxes / --clear-boxes / --remove-boxes /
    # --allowed-boxes）用 nargs="+" + 循环 parse_box，坏坐标会从循环里抛
    # ArgumentTypeError / ValueError 裸 traceback。集中捕获，打印清晰错误并 exit 2，
    # 与 argparse 原生的坏参数行为一致。
    try:
        return args.func(args)
    except argparse.ArgumentTypeError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
