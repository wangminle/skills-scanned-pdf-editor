#!/usr/bin/env python3
"""扫描件文字 / 行带 / 供体定位辅助。

现有技能擅长「已知坐标后的像素操作」；本模块补齐坐标发现：
- 行带检测（纵向墨迹投影）
- 搜索区内墨迹连通域 → 字级候选框
- 按参考框尺寸在供体区搜索相似块

用法示例::

  python3 scripts/locate_content.py lines --source page.png --region 200,400,2200,2800
  python3 scripts/locate_content.py glyphs --source page.png --region 500,800,900,950
  python3 scripts/locate_content.py donors --source page.png \\
      --reference-box 560,820,590,850 --search-region 200,400,2200,2800
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Band:
    y1: int
    y2: int
    ink_ratio: float

    @property
    def height(self) -> int:
        return self.y2 - self.y1


@dataclass(frozen=True)
class GlyphBox:
    x1: int
    y1: int
    x2: int
    y2: int
    area: int

    def as_box(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


def _parse_box(spec: str) -> tuple[int, int, int, int]:
    parts = spec.replace(" ", "").split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"需要 x1,y1,x2,y2，收到: {spec!r}")
    try:
        x1, y1, x2, y2 = (int(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"坐标须为整数: {spec!r}") from exc
    if min(x1, y1, x2, y2) < 0 or x1 >= x2 or y1 >= y2:
        raise argparse.ArgumentTypeError(f"框须非负且有序: {spec!r}")
    return x1, y1, x2, y2


def _to_gray(image: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(image, Image.Image):
        arr = np.asarray(image.convert("RGB"))
    else:
        arr = image
    if arr.ndim == 2:
        return arr.astype(np.uint8)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)


def detect_line_bands(
    image: Image.Image | np.ndarray,
    region: tuple[int, int, int, int] | None = None,
    *,
    ink_threshold: int = 180,
    min_ink_ratio: float = 0.01,
    min_height: int = 8,
    merge_gap: int = 3,
) -> list[Band]:
    """在区域上按纵向墨迹投影检测文字行带。

    返回按 y 排序的 Band 列表（相对整图坐标）。
    """
    gray = _to_gray(image)
    h, w = gray.shape
    if region is None:
        x1, y1, x2, y2 = 0, 0, w, h
    else:
        x1, y1, x2, y2 = region
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x1 >= x2 or y1 >= y2:
            return []

    crop = gray[y1:y2, x1:x2]
    ink = crop < ink_threshold
    row_ratio = ink.mean(axis=1)
    active = row_ratio >= min_ink_ratio

    bands: list[Band] = []
    start = None
    for i, flag in enumerate(active):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            bands.append(_make_band(row_ratio, start, i, y1))
            start = None
    if start is not None:
        bands.append(_make_band(row_ratio, start, len(active), y1))

    # 合并间隙很小的相邻行带
    merged: list[Band] = []
    for band in bands:
        if band.height < min_height:
            continue
        if merged and band.y1 - merged[-1].y2 <= merge_gap:
            prev = merged[-1]
            merged[-1] = Band(
                y1=prev.y1,
                y2=band.y2,
                ink_ratio=max(prev.ink_ratio, band.ink_ratio),
            )
        else:
            merged.append(band)
    return merged


def _make_band(row_ratio: np.ndarray, start: int, end: int, y_offset: int) -> Band:
    seg = row_ratio[start:end]
    return Band(
        y1=y_offset + start,
        y2=y_offset + end,
        ink_ratio=float(seg.mean()) if len(seg) else 0.0,
    )


def detect_glyph_boxes(
    image: Image.Image | np.ndarray,
    region: tuple[int, int, int, int] | None = None,
    *,
    ink_threshold: int = 180,
    min_area: int = 20,
    max_area: int | None = None,
    dilate: int = 1,
) -> list[GlyphBox]:
    """检测搜索区内的墨迹连通域，返回字级候选框（整图坐标）。"""
    gray = _to_gray(image)
    h, w = gray.shape
    if region is None:
        x1, y1, x2, y2 = 0, 0, w, h
    else:
        x1, y1, x2, y2 = region
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x1 >= x2 or y1 >= y2:
            return []

    crop = gray[y1:y2, x1:x2]
    mask = (crop < ink_threshold).astype(np.uint8) * 255
    if dilate > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate * 2 + 1, dilate * 2 + 1))
        mask = cv2.dilate(mask, k, iterations=1)

    n_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out: list[GlyphBox] = []
    area_cap = max_area if max_area is not None else (x2 - x1) * (y2 - y1)
    for i in range(1, n_labels):  # 0 = background
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area or area > area_cap:
            continue
        gx = int(stats[i, cv2.CC_STAT_LEFT])
        gy = int(stats[i, cv2.CC_STAT_TOP])
        gw = int(stats[i, cv2.CC_STAT_WIDTH])
        gh = int(stats[i, cv2.CC_STAT_HEIGHT])
        out.append(
            GlyphBox(
                x1=x1 + gx,
                y1=y1 + gy,
                x2=x1 + gx + gw,
                y2=y1 + gy + gh,
                area=area,
            )
        )
    out.sort(key=lambda b: (b.y1, b.x1))
    return out


def _cluster_into_rows(
    glyphs: list[GlyphBox], ref_h: int,
) -> list[list[GlyphBox]]:
    """把高度合格的连通域按 y 中心聚成行带，同行的按 x 升序。

    y 中心差小于 ``ref_h * 0.5`` 视为同行（参考框高度作为字高估计）。
    跨行但 y 接近的连通域不会被误聚：聚类按 y 中心排序后顺序合并。
    """
    if not glyphs:
        return []
    ordered = sorted(glyphs, key=lambda g: (g.y1 + g.y2) / 2)
    rows: list[list[GlyphBox]] = [[ordered[0]]]
    band_tol = ref_h * 0.5
    for g in ordered[1:]:
        cy = (g.y1 + g.y2) / 2
        prev_cy = (rows[-1][0].y1 + rows[-1][0].y2) / 2
        if abs(cy - prev_cy) <= band_tol:
            rows[-1].append(g)
        else:
            rows.append([g])
    for row in rows:
        row.sort(key=lambda g: g.x1)
    return rows


def _union_glyph_box(group: list[GlyphBox]) -> GlyphBox:
    """合并一组连通域为外接框；area 取并集近似（最大单域×组数上界，足够尺寸比较）。"""
    x1 = min(g.x1 for g in group)
    y1 = min(g.y1 for g in group)
    x2 = max(g.x2 for g in group)
    y2 = max(g.y2 for g in group)
    return GlyphBox(x1=x1, y1=y1, x2=x2, y2=y2, area=sum(g.area for g in group))


def find_donor_candidates(
    image: Image.Image | np.ndarray,
    reference_box: tuple[int, int, int, int],
    search_region: tuple[int, int, int, int] | None = None,
    *,
    ink_threshold: int = 180,
    height_tol: float = 0.25,
    width_tol: float = 0.5,
    max_results: int = 20,
) -> list[tuple[GlyphBox, float]]:
    """在搜索区找与参考框尺寸相近的墨迹块，返回 [(box, score)]，score 越小越近。

    单字符参考框：匹配单个连通域。
    多字符词块参考框（如「结案」）：先按字高过滤连通域，再按 y 中心聚行，
    最后在同行的相邻连通域上做滑动窗口合并，生成多字符组合候选（BUG-067）。
    """
    rx1, ry1, rx2, ry2 = reference_box
    ref_h = ry2 - ry1
    ref_w = rx2 - rx1
    if ref_h <= 0 or ref_w <= 0:
        return []

    glyphs = detect_glyph_boxes(
        image,
        search_region,
        ink_threshold=ink_threshold,
        min_area=max(10, ref_h * ref_w // 8),
        max_area=ref_h * ref_w * 4,
    )

    # 排除与参考框高度重叠的同一块；按字高过滤（单字与多字行成员都需满足）
    height_ok: list[GlyphBox] = []
    for g in glyphs:
        if not (g.x2 <= rx1 or g.x1 >= rx2 or g.y2 <= ry1 or g.y1 >= ry2):
            continue  # 与参考框重叠
        gh = g.y2 - g.y1
        if abs(gh - ref_h) / ref_h > height_tol:
            continue
        height_ok.append(g)

    # 单字符：直接逐个评分（保留原行为）
    candidates: list[tuple[GlyphBox, float]] = []
    for g in height_ok:
        gw = g.x2 - g.x1
        if abs(gw - ref_w) / max(ref_w, 1) > width_tol:
            continue
        score = abs((g.y2 - g.y1) - ref_h) / ref_h + 0.5 * abs(gw - ref_w) / max(ref_w, 1)
        candidates.append((g, score))

    # 多字符：聚行 → 同行相邻连通域滑动窗口合并（BUG-067）
    # 仅当参考框明显比单字宽时才尝试组合（ref_w 超过单字宽度阈值）
    rows = _cluster_into_rows(height_ok, ref_h)
    for row in rows:
        if len(row) < 2:
            continue
        # 滑动窗口大小 2..len(row)：合并相邻连通域为多字块
        for size in range(2, len(row) + 1):
            for start in range(0, len(row) - size + 1):
                group = row[start:start + size]
                merged = _union_glyph_box(group)
                gw = merged.x2 - merged.x1
                gh = merged.y2 - merged.y1
                if abs(gh - ref_h) / ref_h > height_tol:
                    continue
                if abs(gw - ref_w) / max(ref_w, 1) > width_tol:
                    continue
                score = abs(gh - ref_h) / ref_h + 0.5 * abs(gw - ref_w) / max(ref_w, 1)
                candidates.append((merged, score))

    candidates.sort(key=lambda item: item[1])
    return candidates[:max_results]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="扫描件文字/行带/供体定位")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("lines", help="检测行带")
    pl.add_argument("--source", type=Path, required=True)
    pl.add_argument("--region", type=_parse_box, help="搜索区 x1,y1,x2,y2")
    pl.add_argument("--ink-threshold", type=int, default=180)
    pl.add_argument("--min-ink-ratio", type=float, default=0.01)
    pl.add_argument("--min-height", type=int, default=8)
    pl.set_defaults(func=cmd_lines)

    pg = sub.add_parser("glyphs", help="检测字级墨迹框")
    pg.add_argument("--source", type=Path, required=True)
    pg.add_argument("--region", type=_parse_box, help="搜索区 x1,y1,x2,y2")
    pg.add_argument("--ink-threshold", type=int, default=180)
    pg.add_argument("--min-area", type=int, default=20)
    pg.set_defaults(func=cmd_glyphs)

    pd = sub.add_parser("donors", help="按参考框尺寸搜索供体候选")
    pd.add_argument("--source", type=Path, required=True)
    pd.add_argument("--reference-box", type=_parse_box, required=True)
    pd.add_argument("--search-region", type=_parse_box, help="供体搜索区")
    pd.add_argument("--ink-threshold", type=int, default=180)
    pd.add_argument("--max-results", type=int, default=10)
    pd.set_defaults(func=cmd_donors)

    return p


def cmd_lines(args: argparse.Namespace) -> int:
    img = Image.open(args.source)
    bands = detect_line_bands(
        img,
        args.region,
        ink_threshold=args.ink_threshold,
        min_ink_ratio=args.min_ink_ratio,
        min_height=args.min_height,
    )
    print(f"行带数: {len(bands)}")
    for i, b in enumerate(bands):
        print(f"  [{i}] y={b.y1},{b.y2}  h={b.height}  ink_ratio={b.ink_ratio:.3f}")
    return 0


def cmd_glyphs(args: argparse.Namespace) -> int:
    img = Image.open(args.source)
    boxes = detect_glyph_boxes(
        img,
        args.region,
        ink_threshold=args.ink_threshold,
        min_area=args.min_area,
    )
    print(f"候选框数: {len(boxes)}")
    for i, g in enumerate(boxes):
        print(f"  [{i}] {g.x1},{g.y1},{g.x2},{g.y2}  area={g.area}")
    return 0


def cmd_donors(args: argparse.Namespace) -> int:
    img = Image.open(args.source)
    hits = find_donor_candidates(
        img,
        args.reference_box,
        args.search_region,
        ink_threshold=args.ink_threshold,
        max_results=args.max_results,
    )
    print(f"供体候选: {len(hits)}")
    for i, (g, score) in enumerate(hits):
        print(f"  [{i}] {g.x1},{g.y1},{g.x2},{g.y2}  score={score:.3f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (argparse.ArgumentTypeError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
