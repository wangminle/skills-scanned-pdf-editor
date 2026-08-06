#!/usr/bin/env python3
"""扫描版 PDF / 图片局部编辑的统一 CLI。

四种操作模式：
  remove   - 删除指定区域（墨迹蒙版 + Telea 修补 / 行间插值填底）
  move     - 移动原生像素块并清理残留
  replace  - 原生供体替换
  verify   - 像素级验证

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
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import scan_edit_utils as utils


def parse_box(s: str) -> utils.Box:
    parts = s.replace(" ", "").split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"坐标格式应为 x1,y1,x2,y2，收到: {s}")
    return tuple(int(p) for p in parts)


def parse_boxes(s: str) -> list[utils.Box]:
    return [parse_box(b) for b in s.split(";")]


def parse_pair(s: str) -> tuple[int, int]:
    parts = s.replace(" ", "").split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"格式应为 a,b，收到: {s}")
    return tuple(int(p) for p in parts)


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
    content_x = parse_pair(args.content_x)
    source_y = parse_pair(args.source_y)
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
    return 0


# ───────────────────────────── verify ─────────────────────────────


def cmd_compound(args: argparse.Namespace) -> int:
    """复合操作：复制源块 -> 清除多个区域 -> 粘贴源块到新位置。

    适用于 task007 类"先复制再清除"的复合流程（G6）。
    """
    source = load_rgb(args.source)
    content_x = parse_pair(args.content_x)
    source_y = parse_pair(args.source_y)
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
        dark = utils.blank_region_dark_pixels(result, box, threshold=args.blank_threshold)
        print(f"blank_dark_pixels={dark} (threshold<{args.blank_threshold})")
        limit = args.blank_limit if args.blank_limit is not None else 0
        if dark > limit:
            print(f"错误: 空白区深色像素 {dark} 超过上限 {limit}", file=sys.stderr)
            return 1

    if args.preserve_box:
        box = parse_box(args.preserve_box)
        preserved = int(np.count_nonzero(
            np.any(source[box[1]:box[3], box[0]:box[2]] != result[box[1]:box[3], box[0]:box[2]], axis=2)
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
    - --original-pdf 给出时：用 PyMuPDF replace_image 替换内嵌图，保留 OCR 文字层
    - 不给 --original-pdf 时：用 ReportLab 按指定页面尺寸新建 PDF
    """
    from PIL import Image as PILImage
    image = PILImage.open(args.source).convert("RGB")

    if args.original_pdf:
        utils.replace_pdf_image(
            Path(args.original_pdf), args.output, image,
            page_index=args.page_index,
        )
    else:
        if args.page_size:
            parts = args.page_size.replace(" ", "").split(",")
            page_size = (float(parts[0]), float(parts[1]))
        else:
            # 按图像尺寸和 dpi 推算页面点尺寸
            dpi = args.dpi
            page_size = (image.width * 72.0 / dpi, image.height * 72.0 / dpi)
        utils.save_image_as_pdf(
            image, args.output,
            page_size=page_size,
            title=args.title or "",
            subject=args.subject or "",
        )

    print(f"saved: {args.output}")
    return 0


# ───────────────────────────── CLI ─────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="扫描版 PDF / 图片局部编辑：删除、移动、替换、验证。",
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
    pm.add_argument("--content-x", required=True, help="横向范围 x1,x2")
    pm.add_argument("--source-y", required=True, help="纵向范围 y1,y2")
    pm.add_argument("--shift-y", type=int, required=True, help="上移像素数（正值=上移）")
    pm.add_argument("--cleanup-ink-threshold", type=int, default=246, help="残留清理墨迹阈值（默认 246）")
    pm.add_argument("--cleanup-boxes", nargs="+", help="手动指定清理区域（不给则自动用源区域尾部）")
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
    pe.add_argument("--feather", type=int, default=4, help="羽化宽度（默认 4）")
    pe.add_argument("--ink-threshold", type=int, default=180, help="清理墨迹阈值（默认 180）")
    pe.add_argument("--mask-mode", choices=["ink", "full"], default="ink",
                    help="清理蒙版模式：ink=墨迹蒙版（默认），full=整矩形蒙版（G2）")
    pe.add_argument("--normalize-mode", choices=["contrast", "offset"], default="contrast",
                    help="供体归一化模式：contrast=对比度缩放（默认），offset=纯底色偏移（G3）")
    pe.add_argument("--output", type=Path, required=True, help="输出路径")
    pe.add_argument("--crop-box", type=parse_box, help="预览裁剪框")
    pe.add_argument("--save-mask", type=Path, help="保存清理蒙版")
    pe.set_defaults(func=cmd_replace)

    # compound
    pc = sub.add_parser("compound", help="复合操作：复制源块→清除多个区域→粘贴源块到新位置")
    pc.add_argument("--source", type=Path, required=True, help="源图片路径")
    pc.add_argument("--content-x", required=True, help="移动区域横向范围 x1,x2")
    pc.add_argument("--source-y", required=True, help="移动区域纵向范围 y1,y2")
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
    pv.add_argument("--blank-threshold", type=int, default=180, help="空白区深色像素阈值（默认 180）")
    pv.add_argument("--blank-limit", type=int, help="空白区深色像素上限（默认 0）")
    pv.add_argument("--preserve-box", help="应保留不变的区域 x1,y1,x2,y2")
    pv.set_defaults(func=cmd_verify)


    # package
    pp = sub.add_parser("package", help="将编辑后的图片封装为 PDF")
    pp.add_argument("--source", type=Path, required=True, help="编辑后的图片路径")
    pp.add_argument("--output", type=Path, required=True, help="输出 PDF 路径")
    pp.add_argument("--original-pdf", type=Path,
                    help="原始 PDF 路径（给出则用 replace_image 保留 OCR 层；不给则新建 PDF）")
    pp.add_argument("--page-size", help="页面点尺寸 W,H（不给则按 --dpi 从图像推算）")
    pp.add_argument("--dpi", type=int, default=300, help="推算页面尺寸用的 dpi（默认 300）")
    pp.add_argument("--page-index", type=int, default=0, help="替换内嵌图的页码（默认 0）")
    pp.add_argument("--title", help="PDF 标题元数据")
    pp.add_argument("--subject", help="PDF 主题元数据")
    pp.set_defaults(func=cmd_package)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
