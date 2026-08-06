"""扫描版 PDF 编辑结果的泛化验证框架。

支持通过 JSON 配置文件定义多个验证用例，每个用例检查：
- PDF 页数、页面点尺寸
- 300 dpi 回渲与确认 PNG 逐像素一致
- 变化像素数、变化外框
- 允许区域外变化像素 = 0
- 空白行深色像素
- 应保留区域无变化
- 应删区域深色像素
- SHA-256 归档完整性（--strict-hash）
- 复现容差检查（--reproduce）：基准图或可复现管线重跑结果 vs 终版回渲（不是源 vs 终版）

配置文件格式（JSON）:
[
  {
    "name": "用例名称",
    "source_pdf": "path/to/source.pdf",
    "final_pdf": "path/to/final.pdf",
    "expected_image": "path/to/baseline.png",
    "page_size": [595.2, 841.68],
    "expected_sha256": "...",
    "allowed_boxes": [[x1,y1,x2,y2], ...],
    "expected_changed_pixels": 1577499,
    "expected_changed_bbox": [x1,y1,x2,y2],
    "blank_box": [x1,y1,x2,y2],
    "blank_dark_limit": 0,
    "preserve_box": [x1,y1,x2,y2],
    "dark_box": [x1,y1,x2,y2],
    "dark_threshold": 210,
    "dark_limit": 0,
    "render_backend": "pdfium",
    "reproduce_command": "可选：可复现的处理管线重跑命令（shell 执行，产出写入 reproduce_image）",
    "reproduce_image": "可选：reproduce_command 的重算输出图路径，供 --reproduce 容差比较",
    "expected_pages": 1,
    "page_index": 0
  }
]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

import scan_edit_utils as utils

# --reproduce 模式的容差：OpenCV Telea 在不同版本/平台上可能有极小舍入差异。
REPRODUCE_MAX_CHANGED_PIXELS = 10_000
REPRODUCE_MAX_CHANNEL_DIFF = 4
REPRODUCE_MAX_MAE = 0.001


@dataclass(frozen=True)
class VerifyCase:
    name: str
    source_pdf: Path
    final_pdf: Path
    expected_image: Path | None = None
    page_size: tuple[float, float] | None = None
    expected_sha256: str | None = None
    allowed_boxes: tuple[utils.Box, ...] = ()
    expected_changed_pixels: int | None = None
    expected_changed_bbox: utils.Box | None = None
    blank_box: utils.Box | None = None
    blank_dark_limit: int = 0
    preserve_box: utils.Box | None = None
    dark_box: utils.Box | None = None
    dark_threshold: int = 180
    dark_limit: int = 0
    render_backend: str = "pdfium"
    render_dpi: int = 300
    reproduce_command: str | None = None
    reproduce_image: Path | None = None
    # 多页支持：默认页数 1（兼容旧配置）、默认验证第 1 页（page_index=0）。
    # package --page-index 可封装多页 PDF 中的指定页，这里按配置验证对应页。
    expected_pages: int = 1
    page_index: int = 0


def load_config(config_path: Path) -> list[VerifyCase]:
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cases = []
    for item in data:
        cases.append(VerifyCase(
            name=item["name"],
            source_pdf=Path(item["source_pdf"]),
            final_pdf=Path(item["final_pdf"]),
            expected_image=Path(item["expected_image"]) if item.get("expected_image") else None,
            page_size=tuple(item["page_size"]) if item.get("page_size") else None,
            expected_sha256=item.get("expected_sha256"),
            allowed_boxes=tuple(tuple(b) for b in item["allowed_boxes"]) if item.get("allowed_boxes") else (),
            expected_changed_pixels=item.get("expected_changed_pixels"),
            expected_changed_bbox=tuple(item["expected_changed_bbox"]) if item.get("expected_changed_bbox") else None,
            blank_box=tuple(item["blank_box"]) if item.get("blank_box") else None,
            blank_dark_limit=item.get("blank_dark_limit", 0),
            preserve_box=tuple(item["preserve_box"]) if item.get("preserve_box") else None,
            dark_box=tuple(item["dark_box"]) if item.get("dark_box") else None,
            dark_threshold=item.get("dark_threshold", 180),
            dark_limit=item.get("dark_limit", 0),
            render_backend=item.get("render_backend", "pdfium"),
            render_dpi=item.get("render_dpi", 300),
            reproduce_command=item.get("reproduce_command"),
            reproduce_image=Path(item["reproduce_image"]) if item.get("reproduce_image") else None,
            expected_pages=item.get("expected_pages", 1),
            page_index=item.get("page_index", 0),
        ))
    return cases


def render_case_page(
    path: Path, backend: str, dpi: int, *, page_index: int = 0
) -> np.ndarray:
    if backend == "pdfium":
        return np.asarray(utils.render_pdf_page(path, page_index=page_index, dpi=dpi))
    if backend == "pymupdf":
        import fitz
        document = fitz.open(str(path))
        page = document[page_index]
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False
        )
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )[..., :3].copy()
        document.close()
        return image
    raise ValueError(f"未知渲染后端：{backend}")


def page_info_at(path: Path, page_index: int = 0) -> tuple[int, tuple[float, float]]:
    """返回 (总页数, 第 page_index 页的点尺寸)。"""
    document = utils.pdfium.PdfDocument(str(path))
    try:
        if not len(document):
            raise ValueError(f"PDF 没有页面: {path}")
        if not 0 <= page_index < len(document):
            raise IndexError(f"页码越界: {page_index + 1}/{len(document)}")
        size = tuple(float(v) for v in document[page_index].get_size())
        return len(document), size
    finally:
        document.close()


def close_size(actual: tuple[float, float], expected: tuple[float, float]) -> bool:
    return all(abs(a - e) <= 0.02 for a, e in zip(actual, expected))


def verify(case: VerifyCase, *, strict_hash: bool, reproduce: bool = False) -> list[str]:
    errors: list[str] = []

    # 页数：终版总页数应与配置的预期一致（默认 1，兼容旧配置）。
    # 不再无条件要求单页，否则 package --page-index 支持的多页 PDF 即使未改也会失败。
    pages, page_size = page_info_at(case.final_pdf, case.page_index)
    if pages != case.expected_pages:
        errors.append(f"页数应为 {case.expected_pages}，实际为 {pages}")
    if case.page_size and not close_size(page_size, case.page_size):
        errors.append(
            f"第 {case.page_index + 1} 页尺寸应为 {case.page_size}，实际为 {page_size}"
        )

    # SHA-256
    if case.expected_sha256:
        digest = utils.sha256_file(case.final_pdf)
        if digest != case.expected_sha256:
            message = f"SHA-256 与归档值不同: {digest}"
            if strict_hash:
                errors.append(message)
            else:
                print(f"  警告：{message}")

    # 300 dpi 回渲：按配置验证目标页（默认第 1 页），而非永远渲染第 1 页。
    final = render_case_page(
        case.final_pdf, case.render_backend, case.render_dpi, page_index=case.page_index
    )

    # 与确认基准图比对（--reproduce 模式不要求逐像素一致，改走下方容差比较）
    if case.expected_image and not reproduce:
        expected = np.asarray(Image.open(case.expected_image).convert("RGB"))
        if final.shape != expected.shape or not np.array_equal(final, expected):
            errors.append("PDF 的 300 dpi 回渲结果与确认基准图不完全一致")
            return errors

    # 与原图差分：源 PDF 取同一目标页。
    source = render_case_page(
        case.source_pdf, case.render_backend, case.render_dpi, page_index=case.page_index
    )
    stats = utils.image_diff(source, final)

    if case.expected_changed_pixels is not None and stats.changed_pixels != case.expected_changed_pixels:
        errors.append(f"变化像素应为 {case.expected_changed_pixels}，实际为 {stats.changed_pixels}")
    if case.expected_changed_bbox and stats.bbox != case.expected_changed_bbox:
        errors.append(f"变化外框应为 {case.expected_changed_bbox}，实际为 {stats.bbox}")

    # 允许区域外变化
    if case.allowed_boxes:
        outside = utils.changes_outside_boxes(source, final, case.allowed_boxes)
        if outside:
            errors.append(f"允许区域外出现 {outside} 个变化像素")

    # 空白行检查
    if case.blank_box:
        dark = utils.blank_region_dark_pixels(final, case.blank_box, threshold=180)
        if dark > case.blank_dark_limit:
            errors.append(f"预留空白区深色像素为 {dark}，上限为 {case.blank_dark_limit}")
        print(f"  空白区深色像素（亮度<180）：{dark}")

    # 应保留区域
    if case.preserve_box:
        x1, y1, x2, y2 = case.preserve_box
        preserved = int(np.count_nonzero(
            np.any(source[y1:y2, x1:x2] != final[y1:y2, x1:x2], axis=2)
        ))
        if preserved:
            errors.append(f"应保留区域出现 {preserved} 个变化像素")
        print(f"  应保留区域变化像素：{preserved}")

    # 应删区域
    if case.dark_box:
        dark = utils.blank_region_dark_pixels(final, case.dark_box, threshold=case.dark_threshold)
        if dark > case.dark_limit:
            errors.append(f"应删区域深色像素为 {dark}，上限为 {case.dark_limit}")
        print(f"  应删区域深色像素（亮度<{case.dark_threshold}）：{dark}")

    print(
        f"  {case.render_dpi}dpi={final.shape[1]}×{final.shape[0]}，"
        f"变化像素={stats.changed_pixels}，范围={stats.bbox}"
    )

    # --reproduce：基准图（或可复现管线重跑结果）与终版 PDF 回渲做容差比较。
    # 原语义：在内存中重跑处理管线，把重算结果与归档基准比，容差用于吸收
    # OpenCV Telea 等在不同版本/平台的微小舍入差异。
    # 泛化实现：基准 = reproduce_command 的产出图（给出时），否则 expected_image 基准图。
    if reproduce:
        baseline = None
        if case.reproduce_command:
            if not case.reproduce_image:
                errors.append("reproduce_command 需要同时给出 reproduce_image 指定重算图路径")
            else:
                completed = subprocess.run(
                    case.reproduce_command, shell=True, capture_output=True, text=True,
                )
                if completed.returncode != 0:
                    errors.append(
                        f"reproduce_command 退出码 {completed.returncode}: "
                        f"{completed.stderr.strip()[:500]}"
                    )
                elif not case.reproduce_image.exists():
                    errors.append(f"reproduce_command 未产出重算图: {case.reproduce_image}")
                else:
                    baseline = np.asarray(Image.open(case.reproduce_image).convert("RGB"))
        elif case.expected_image:
            baseline = np.asarray(Image.open(case.expected_image).convert("RGB"))
        else:
            errors.append("--reproduce 需要配置 expected_image 或 reproduce_command + reproduce_image")

        if baseline is not None:
            if baseline.shape != final.shape:
                errors.append(
                    f"reproduce 基准图尺寸 {baseline.shape[:2]} 与终版回渲 {final.shape[:2]} 不一致"
                )
            else:
                diff = np.abs(baseline.astype(np.int16) - final.astype(np.int16))
                changed_pixels = int(np.any(diff > 0, axis=2).sum())
                max_channel = int(diff.max())
                mae = float(diff.mean())
                print(f"  reproduce: changed={changed_pixels}, max_channel_diff={max_channel}, MAE={mae:.6f}")
                if changed_pixels > REPRODUCE_MAX_CHANGED_PIXELS:
                    errors.append(f"reproduce 变化像素 {changed_pixels} 超过容差 {REPRODUCE_MAX_CHANGED_PIXELS}")
                if max_channel > REPRODUCE_MAX_CHANNEL_DIFF:
                    errors.append(f"reproduce 单通道最大差 {max_channel} 超过容差 {REPRODUCE_MAX_CHANNEL_DIFF}")
                if mae > REPRODUCE_MAX_MAE:
                    errors.append(f"reproduce MAE {mae:.6f} 超过容差 {REPRODUCE_MAX_MAE}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, required=True,
        help="验证配置 JSON 文件路径",
    )
    parser.add_argument(
        "--strict-hash", action="store_true",
        help="将 PDF 文件哈希不一致视为失败（不只警告）",
    )
    parser.add_argument(
        "--reproduce", action="store_true",
        help="基准图（expected_image）或 reproduce_command 重跑结果与终版 PDF 回渲做容差比较（≤10000px / 通道差≤4 / MAE≤0.001）",
    )
    args = parser.parse_args()

    cases = load_config(args.config)
    all_errors: list[str] = []
    for case in cases:
        print(f"[{case.name}]")
        errors = verify(case, strict_hash=args.strict_hash, reproduce=args.reproduce)
        if errors:
            all_errors.extend(f"{case.name}：{error}" for error in errors)
        else:
            print("  通过")

    if all_errors:
        print("\n复核失败：", file=sys.stderr)
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"\n{len(cases)} 份终版全部通过复核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
