#!/usr/bin/env python3
"""对齐新增文字与原文行的垂直中心。

问题: scan_text_fusion.py 用 --position X Y 指定文字绘制起点（PIL text 的左上角），
但不同字体的 ascent/descent 不同，相同的 Y 产生的墨迹视觉中心不同。若用户把 Y
设为原文行上沿，新增文字可能偏高或偏低几像素。

典型案例: task001 新增"实习律师"的墨迹 y 重心比原文低 4.1px，肉眼可见不对齐。

本工具: 取原文行上参考字的框，计算其墨迹垂直中心；再渲染目标字体/字号
的文字并计算其墨迹垂直中心相对于绘制起点的偏移；输出调整后的 Y 值，
使新增文字的墨迹中心与参考字对齐。

用法:
  python align_text.py --source page.png \\
      --ref-box 558,557,587,585 \\
      --font 仿宋 --size 32 --text 实习律师 --y 557

  # 多字参考（取平均中心更稳定）:
  python align_text.py --source page.png \\
      --ref-box 558,557,587,585 --ref-box 587,557,614,585 \\
      --font simfang.ttf --size 32 --text 实习律师 --y 557

输出: 调整后的 Y 值及与原始 Y 的偏差，直接用于 scan_text_fusion.py --position。
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFont, ImageDraw

import font_registry

INK_THR = 160  # 与 identify_font.py 一致


def ink_vertical_center(gray, thr=INK_THR):
    """计算灰度图中墨迹的垂直重心（暗像素 y 坐标均值）。

    返回 None 表示无墨迹。用重心而非外接框中心，因为重心对个别笔画
    位置不敏感（如'三'字上空下密，外接框中心偏高，重心更准）。
    """
    m = gray < thr
    if not m.any():
        return None
    ys, _ = np.where(m)
    return float(ys.mean())


def text_ink_center_offset(text, font_path, font_index, size, thr=INK_THR):
    """渲染文字并返回墨迹垂直中心相对于绘制起点 (y=0) 的偏移。

    PIL ImageDraw.text((x, y), ...) 中 y 是字体上沿（ascender 顶部），
    但实际墨迹上沿与 y 的距离因字体而异（ascent 差异）。本函数在
    (size, size) 处渲染文字，计算墨迹垂直中心，再减去绘制 y(=size)
    得到"若画在 y=0 处，墨迹中心在哪个 y"。
    """
    font = ImageFont.truetype(font_path, size, index=font_index)
    canvas_w = size * (len(text) + 2)
    canvas_h = size * 3
    canvas = Image.new('L', (canvas_w, canvas_h), 255)
    ImageDraw.Draw(canvas).text((size, size), text, font=font, fill=0)
    arr = np.asarray(canvas).astype(np.float32)
    center = ink_vertical_center(arr, thr)
    if center is None:
        return None
    return center - size


def parse_box(s, name="--ref-box", image_size=None):
    """解析 x1,y1,x2,y2 格式的字符串。

    image_size=(W,H) 给出时，额外校验框完整落在图像内（BUG-061）——
    越界框在 numpy 切片中会被静默截小，导致墨迹中心计算偏移。
    """
    parts = [v.strip() for v in s.split(',')]
    if len(parts) != 4:
        raise SystemExit(f"错误: {name} 需为 4 个值 x1,y1,x2,y2，收到 {len(parts)} 个: {s!r}")
    try:
        x1, y1, x2, y2 = (int(v) for v in parts)
    except ValueError:
        raise SystemExit(f"错误: {name} 需为整数，收到: {s!r}")
    if x1 < 0 or y1 < 0 or x2 < 0 or y2 < 0:
        raise SystemExit(f"错误: {name} 需全部非负，收到: {s!r}")
    if x1 >= x2 or y1 >= y2:
        raise SystemExit(f"错误: {name} 需满足 x1<x2 且 y1<y2，收到: {s!r}")
    if image_size is not None:
        img_w, img_h = image_size
        if x2 > img_w or y2 > img_h:
            raise SystemExit(
                f"错误: {name} {s!r} 越出图像边界 {img_w}×{img_h}，"
                "请核对坐标是否为该图像内的像素坐标。"
            )
    return (x1, y1, x2, y2)


def main():
    ap = argparse.ArgumentParser(
        description='计算新增文字与原文行对齐的 Y 坐标（墨迹垂直中心匹配）')
    ap.add_argument('--source', required=True, help='源扫描图 (PNG)')
    ap.add_argument('--ref-box', action='append', required=True,
                    metavar='X1,Y1,X2,Y2',
                    help='原文行上参考字的框，可多次给出（多字取平均中心更稳定）')
    ap.add_argument('--font', required=True,
                    help='新增文字的字体（路径/注册名/文件名）')
    ap.add_argument('--font-index', type=int, default=0,
                    help='ttc 字体索引（默认 0）')
    ap.add_argument('--size', type=int, required=True,
                    help='字号（像素，与 scan_text_fusion --font-size 一致）')
    ap.add_argument('--text', required=True,
                    help='新增文字内容（用于计算墨迹中心偏移）')
    ap.add_argument('--y', type=int, required=True,
                    help='原始计划的 Y 坐标（scan_text_fusion --position 的 Y）')
    args = ap.parse_args()

    # 加载源图
    im = Image.open(args.source).convert('L')
    arr = np.asarray(im).astype(np.float32)

    # 计算参考字的墨迹垂直中心（在源图坐标系中）
    ref_centers = []
    for spec in args.ref_box:
        box = parse_box(spec, image_size=im.size)
        x1, y1, x2, y2 = box
        region = arr[y1:y2, x1:x2]
        c = ink_vertical_center(region)
        if c is None:
            print(f'警告: 框 {box} 内无墨迹，跳过。', file=sys.stderr)
            continue
        # c 是相对于 region 上沿的中心，转回源图坐标
        ref_centers.append(y1 + c)
    if not ref_centers:
        print('错误: 所有参考框内均无墨迹', file=sys.stderr)
        sys.exit(1)
    ref_center_y = sum(ref_centers) / len(ref_centers)
    src_label = f'{len(ref_centers)} 个参考框的平均值' if len(ref_centers) > 1 else '单参考框'
    print(f'参考字墨迹垂直中心: Y={ref_center_y:.1f} ({src_label})')

    # 解析字体
    if args.font and not Path(args.font).exists():
        resolved = font_registry.find_font(args.font)
        if resolved is None:
            raise SystemExit(f"错误: 找不到字体 {args.font!r}")
        font_path, font_index = resolved
    else:
        font_path, font_index = args.font, args.font_index
    print(f'字体: {font_path} (index={font_index})  字号: {args.size}')

    # 计算渲染文字的墨迹中心偏移（相对于绘制起点 y=0）
    offset = text_ink_center_offset(args.text, font_path, font_index, args.size)
    if offset is None:
        print('错误: 渲染文字无墨迹，检查字体/字号/文字内容', file=sys.stderr)
        sys.exit(1)
    print(f'渲染文字墨迹中心偏移: {offset:.1f}px (相对于绘制起点)')

    # 调整后的 Y = 参考中心 - 渲染偏移
    adjusted_y = round(ref_center_y - offset)
    delta = adjusted_y - args.y
    print(f'\n=> 调整后 Y = {adjusted_y}  (原始 Y={args.y}, 偏差={delta:+d}px)')
    if delta != 0:
        direction = '下移' if delta > 0 else '上移'
        print(f'   需{direction} {abs(delta)}px 使墨迹中心与原文对齐')
    else:
        print('   原始 Y 已对齐，无需调整')
    print(f'   使用: scan_text_fusion.py --position <X> {adjusted_y} ...')


if __name__ == '__main__':
    main()
