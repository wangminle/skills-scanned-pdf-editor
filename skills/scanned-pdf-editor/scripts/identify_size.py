"""程序化字号识别：墨迹尺寸匹配（高+宽，多字聚合）× 多暗核阈值共识。
为什么需要它：单字墨迹高度（尤其'甜'这种近满框字）+ 松阈值会低估/高估字号 1 档，
迫使人工 +1。本工具用"墨迹高+宽相对误差"在多个暗核阈值(80~120)上各取最优字号，
取中位数共识，避开扫描虚化晕(>120 会膨胀墨框)。

用法：
  python identify_size.py --source page.png --font C:/Windows/Fonts/simfang.ttf \
      --ref 田=558,557,587,585 --ref 甜=587,557,614,585

--font 支持三种写法（同 identify_font.py，统一走 font_registry）：
  完整路径、注册名（如 '仿宋'/'宋体'，模糊匹配）、纯文件名（如 simfang.ttf）。

输出：各阈值推荐字号 + 中位数共识 = 推荐字号。
配合 identify_font.py：先用前者定字体，再用本工具定字号，全程程序化、可追溯。
"""
import os
import sys
import argparse
import numpy as np
from PIL import Image, ImageFont, ImageDraw

import font_registry

def ink_dims(arr, thr):
    m = arr < thr
    if m.sum() < 5:
        return None
    ys, xs = np.where(m)
    return (ys.max()-ys.min()+1, xs.max()-xs.min()+1)

def render_glyph(char, font_path, size, idx=0):
    f = ImageFont.truetype(font_path, size, index=idx)
    pad = size + 4
    img = Image.new('L', (size*3+pad*2, size*3+pad*2), 255)
    ImageDraw.Draw(img).text((pad, pad), char, font=f, fill=0)
    return np.asarray(img).astype(np.float32)

def best_size_for_threshold(font_path, font_index, refs_scan_dims, sizes, thr):
    """单阈值下，遍历字号取合计相对误差最小的。"""
    agg = {}
    for sz in sizes:
        total = 0.0
        n = 0
        for ch, sd in refs_scan_dims:
            rd = ink_dims(render_glyph(ch, font_path, sz, font_index), thr)
            if rd is None or sd is None:
                continue
            total += abs(rd[0]-sd[0])/sd[0] + abs(rd[1]-sd[1])/sd[1]
            n += 1
        agg[sz] = total/n if n else 9e9
    best = min(agg, key=agg.get)
    return best, agg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--font', required=True, help='字体路径、注册名（如 仿宋/宋体）或文件名（如 simfang.ttf）')
    ap.add_argument('--font-index', type=int, default=0, help='ttc 索引，仅 --font 为显式路径时生效')
    ap.add_argument('--ref', action='append', required=True, help='字=x1,y1,x2,y2')
    ap.add_argument('--sizes', default='27,28,29,30,31,32,33,34,35,36')
    ap.add_argument('--thresholds', default='80,90,100,110,120')
    args = ap.parse_args()

    # --font 解析：显式路径直接用 + --font-index；注册名/文件名走 font_registry（含 ttc 索引）。
    if os.path.exists(args.font):
        font_path, font_index = args.font, args.font_index
    else:
        resolved = font_registry.find_font(args.font)
        if resolved is None:
            print(
                f"错误: 无法按 --font \"{args.font}\" 找到字体。支持完整路径、"
                "注册名（如 仿宋/宋体）或文件名（如 simfang.ttf）。",
                file=sys.stderr,
            )
            sys.exit(2)
        font_path, font_index = resolved

    arr = np.asarray(Image.open(args.source).convert('L')).astype(np.float32)
    sizes = [int(s) for s in args.sizes.split(',')]
    thrs = [int(t) for t in args.thresholds.split(',')]

    refs_dims = []
    for r in args.ref:
        ch, box = r.split('=')
        x1, y1, x2, y2 = [int(v) for v in box.split(',')]
        refs_dims.append((ch, arr[y1:y2, x1:x2]))

    print('=== 字号识别（墨迹尺寸匹配 × 多暗核阈值共识）===')
    print(f'字体: {font_path}    参考字: {",".join(ch for ch,_ in refs_dims)}\n')

    # 预检：在最高阈值下（最容易抓到墨迹）若任一参考框抓不到有效墨迹，
    # 说明框选错位/空白/无墨迹，后续所有阈值都会落入 9e9 误差并退化为"选首项字号"，
    # 产生虚假的高置信结论。先拒绝，避免给出误导性推荐。
    # ink_dims 用 arr < thr 判定墨迹，thr 越高越宽松（更多像素算墨迹），
    # 所以 max(thrs) 是最宽松的检测条件。
    blank_refs = [ch for ch, crop in refs_dims if ink_dims(crop, max(thrs)) is None]
    if blank_refs:
        print(f'错误: 以下参考框在最高阈值 {max(thrs)} 下未检测到有效墨迹（可能为空白/框选错位）:'
              f' {", ".join(blank_refs)}\n'
              '建议：重新框选参考字，确保框内有清晰的墨迹。', file=sys.stderr)
        sys.exit(3)

    recs = []
    for thr in thrs:
        scan_dims = [(ch, ink_dims(crop, thr)) for ch, crop in refs_dims]
        best, agg = best_size_for_threshold(font_path, font_index, scan_dims, sizes, thr)
        recs.append(best)
        dims_str = ' '.join(f'{ch}:h{d[0]}w{d[1]}' for ch, d in scan_dims if d)
        print(f'  thr {thr:>3} → 字号 {best:>2}  (误差 {agg[best]:.3f})   scan墨迹 {dims_str}')

    consensus = int(np.median(recs))
    # 置信度门：阈值间共识度。全阈值一致或仅 1 个偏离 = 确定；否则存疑。
    agree = sum(1 for r in recs if r == consensus)
    n = len(recs)
    if agree >= n - 1:
        verdict = '确定（阈值间共识充分）'
        hint = ''
    else:
        verdict = '存疑（阈值间分歧明显）'
        hint = '\n建议：增加 1~2 个参考字（尤其结构不同的字），或框选更清晰的字以稳定墨迹尺寸。'
    print(f'\n推荐字号（中位数共识）: {consensus}   [{verdict}]')
    print(f'阈值一致: {agree}/{n} 个阈值给出 {consensus}。')
    print('说明：暗核阈值(80~110)稳定；>120 受扫描虚化晕影响会偏高 1 档，已由中位数平滑掉。' + hint)

if __name__ == '__main__':
    main()
