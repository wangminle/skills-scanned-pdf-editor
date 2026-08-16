#!/usr/bin/env python3
"""扫描件版式的可复核像素测量工具。

提供行带、墨迹框、字距/碰撞、基线与移动量测量，所有输出均为 JSON，
便于直接写入处理记录或由后续命令消费。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import locate_content
import scan_edit_utils as utils


def parse_box(spec: str) -> utils.Box:
    try:
        return locate_content._parse_box(spec)
    except argparse.ArgumentTypeError:
        raise


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def mask_in_box(image: np.ndarray, box: utils.Box, threshold: int) -> np.ndarray:
    x1, y1, x2, y2 = box
    h, w = image.shape[:2]
    if x2 > w or y2 > h:
        raise ValueError(f"框 {box} 越出图像 {w}×{h}")
    mask = np.zeros((h, w), dtype=bool)
    mask[y1:y2, x1:x2] = utils.luma(image[y1:y2, x1:x2]) < threshold
    return mask


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_lines(args: argparse.Namespace) -> int:
    image = load_rgb(args.source)
    bands = locate_content.detect_line_bands(
        image,
        args.region,
        ink_threshold=args.ink_threshold,
        min_ink_ratio=args.min_ink_ratio,
        min_height=args.min_height,
        merge_gap=args.merge_gap,
    )
    payload = []
    for index, band in enumerate(bands):
        payload.append({
            "index": index,
            "y1": band.y1,
            "y2": band.y2,
            "height": band.height,
            "ink_ratio": round(band.ink_ratio, 8),
            "gap_from_previous": None if index == 0 else band.y1 - bands[index - 1].y2,
            "top_distance_from_previous": None if index == 0 else band.y1 - bands[index - 1].y1,
        })
    print_json({"threshold": args.ink_threshold, "region": args.region, "bands": payload})
    return 0


def cmd_ink_bbox(args: argparse.Namespace) -> int:
    image = load_rgb(args.source)
    box = utils.ink_bbox(image, args.region, threshold=args.ink_threshold)
    count = 0
    if box:
        count = utils.blank_region_dark_pixels(image, box, threshold=args.ink_threshold)
    print_json({
        "threshold": args.ink_threshold,
        "region": args.region,
        "ink_bbox": box,
        "ink_pixels": count,
    })
    return 0 if box else 1


def cmd_gap(args: argparse.Namespace) -> int:
    image = load_rgb(args.source)
    left = mask_in_box(image, args.left_box, args.ink_threshold)
    right = mask_in_box(image, args.right_box, args.ink_threshold)
    ly, lx = np.where(left)
    ry, rx = np.where(right)
    if not len(lx) or not len(rx):
        raise ValueError("左右测量框至少有一个未检测到墨迹")

    collision = int(np.count_nonzero(left & right))
    horizontal_gap = int(rx.min() - lx.max() - 1)
    vertical_overlap = int(min(ly.max(), ry.max()) - max(ly.min(), ry.min()) + 1)
    if collision:
        nearest = 0.0
    else:
        distance = cv2.distanceTransform((~right).astype(np.uint8), cv2.DIST_L2, 5)
        nearest = float(distance[left].min())
    left_bbox = utils.ink_bbox(image, args.left_box, threshold=args.ink_threshold)
    right_bbox = utils.ink_bbox(image, args.right_box, threshold=args.ink_threshold)
    baseline_delta = right_bbox[3] - left_bbox[3]
    center_delta = ((right_bbox[1] + right_bbox[3]) - (left_bbox[1] + left_bbox[3])) / 2.0
    print_json({
        "threshold": args.ink_threshold,
        "left_ink_bbox": left_bbox,
        "right_ink_bbox": right_bbox,
        "collision_pixels": collision,
        "horizontal_gap_px": horizontal_gap,
        "nearest_gap_px": round(nearest, 3),
        "vertical_overlap_px": vertical_overlap,
        "baseline_delta_px": baseline_delta,
        "center_delta_px": center_delta,
    })
    return 0


def cmd_shift(args: argparse.Namespace) -> int:
    image = load_rgb(args.source)
    source = utils.ink_bbox(image, args.source_box, threshold=args.ink_threshold)
    target = utils.ink_bbox(image, args.target_box, threshold=args.ink_threshold)
    if not source or not target:
        raise ValueError("源框或目标框未检测到墨迹")
    print_json({
        "threshold": args.ink_threshold,
        "source_ink_bbox": source,
        "target_ink_bbox": target,
        "top_shift_px": source[1] - target[1],
        "baseline_shift_px": source[3] - target[3],
        "center_shift_px": ((source[1] + source[3]) - (target[1] + target[3])) / 2.0,
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    lines = sub.add_parser("lines", help="测量行带、行高与行距")
    lines.add_argument("--source", type=Path, required=True)
    lines.add_argument("--region", type=parse_box)
    lines.add_argument("--ink-threshold", type=int, default=220)
    lines.add_argument("--min-ink-ratio", type=float, default=0.005)
    lines.add_argument("--min-height", type=int, default=3)
    lines.add_argument("--merge-gap", type=int, default=3)
    lines.set_defaults(func=cmd_lines)

    bbox = sub.add_parser("ink-bbox", help="测量区域内墨迹最小外接框")
    bbox.add_argument("--source", type=Path, required=True)
    bbox.add_argument("--region", type=parse_box)
    bbox.add_argument("--ink-threshold", type=int, default=220)
    bbox.set_defaults(func=cmd_ink_bbox)

    gap = sub.add_parser("gap", help="测量两组墨迹的碰撞、最近距离、字距和基线")
    gap.add_argument("--source", type=Path, required=True)
    gap.add_argument("--left-box", type=parse_box, required=True)
    gap.add_argument("--right-box", type=parse_box, required=True)
    gap.add_argument("--ink-threshold", type=int, default=220)
    gap.set_defaults(func=cmd_gap)

    shift = sub.add_parser("shift", help="按两处墨迹顶端/基线/中心测量移动量")
    shift.add_argument("--source", type=Path, required=True)
    shift.add_argument("--source-box", type=parse_box, required=True)
    shift.add_argument("--target-box", type=parse_box, required=True)
    shift.add_argument("--ink-threshold", type=int, default=220)
    shift.set_defaults(func=cmd_shift)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
