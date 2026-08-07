#!/usr/bin/env python3
"""识别扫描件原文字体 —— 灰度 NCC + 高度归一化 + 多字聚合（必做步骤，不可凭肉眼猜）。

每份扫描件的字体都可能不同，**不要沿用上一份任务用过的字体**：必须当场识别。
凭肉眼/经验猜（"看起来像宋体/黑体"）很容易错——人们常把所有衬线中文字统称"宋体"，
但宋体和仿宋是不同字体。用本工具程序化判定。

方法：从扫描里裁若干笔画清晰的既有字；对每个候选字体在同一批字上做"渲染字号 × 平移"
搜索，把候选与扫描字都高度归一化后算灰度归一化互相关（NCC），多字得分求和，NCC 总分
最高者即原文字体。NCC 对亮度/对比度线性变化不敏感，故能抗扫描件墨色深浅差异。

用法:
  python identify_font.py --source page.png \\
      --ref 田=558,557,587,585 --ref 甜=587,557,614,585

  # 限定候选字体（默认覆盖常见中文字）:
  python identify_font.py --source page.png --ref 田=558,557,587,585 \\
      --candidates "仿宋=simfang.ttf,宋体=simsun.ttc,黑体=simhei.ttf,等线=Deng.ttf"

判定：总分最高且**衬线明显优于无衬线**才可信。中文公文正文常为仿宋、标题常为小标宋/
黑体——但都以本工具结果为准，不要用经验覆盖实测。

置信度不足（参考/存疑）且有候选字体未安装时，脚本会提示可能因目标字体缺失、并给出
安装路径（macOS ~/Library/Fonts、Windows C:\\Windows\\Fonts）。装上后重跑即可。
"""
import argparse
import sys
import numpy as np
from PIL import Image, ImageFont, ImageDraw

import font_registry

# 默认候选表与字体目录解析统一走 font_registry，避免两份脚本各自维护、漂移。
CJK_CANDIDATES = font_registry.CJK_FONTS
resolve_font = font_registry.resolve_font

HN = 48          # 高度归一化像素
INK_THR = 160    # 取墨迹外接框用的阈值（偏高以捕获扫描模糊边缘全形）
SIZES = [28, 30, 32, 34, 36, 40]


def ink_bbox(gray, thr=INK_THR):
    m = gray < thr
    if not m.any():
        return None
    ys, xs = np.where(m)
    return gray[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def norm_height(gray, h=HN):
    pil = Image.fromarray(np.uint8(np.clip(gray, 0, 255)), 'L')
    w = max(1, int(round(gray.shape[1] * h / gray.shape[0])))
    return np.asarray(pil.resize((w, h), Image.BILINEAR)).astype(np.float32)


def ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    na = np.sqrt((a * a).sum())
    nb = np.sqrt((b * b).sum())
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    return float((a * b).sum() / (na * nb))


def render_glyph(char, font_path, idx, size):
    font = ImageFont.truetype(font_path, size, index=idx)
    canvas = Image.new('L', (size * 3, size * 3), 255)
    ImageDraw.Draw(canvas).text((size, size), char, font=font, fill=0)
    return ink_bbox(np.asarray(canvas).astype(np.float32))


def best_ncc(target_gray, font_path, idx, char):
    """高度归一化后在 size×shift 上搜最大 NCC。"""
    t = norm_height(target_gray)
    th, tw = t.shape
    best = 0.0
    for size in SIZES:
        g = render_glyph(char, font_path, idx, size)
        if g is None:
            continue
        gn = norm_height(g)
        gh, gw = gn.shape
        if gw >= tw:
            for x0 in range(0, gw - tw + 1):
                sub = gn[:, x0:x0 + tw]
                for dy in range(-2, 3):
                    cand = np.zeros_like(t)
                    y0 = max(0, min((th - gh) // 2 + dy, max(th - gh, 0))) if gh <= th else 0
                    if gh <= th:
                        cand[y0:y0 + gh, :] = sub
                    else:
                        cand[:, :] = sub[:th, :]
                    v = ncc(t, cand)
                    if v > best:
                        best = v
        else:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    cand = np.zeros_like(t)
                    y0 = (th - gh) // 2 + dy
                    x0 = (tw - gw) // 2 + dx
                    yy0, xx0 = max(0, y0), max(0, x0)
                    yy1, xx1 = min(th, y0 + gh), min(tw, x0 + gw)
                    if yy1 > yy0 and xx1 > xx0:
                        cand[yy0:yy1, xx0:xx1] = gn[max(0, -y0):max(0, -y0) + (yy1 - yy0),
                                                     max(0, -x0):max(0, -x0) + (xx1 - xx0)]
                        v = ncc(t, cand)
                        if v > best:
                            best = v
    return best


def glyph_fingerprint(gray, thr=INK_THR):
    """计算字形指纹：墨迹密度、水平/垂直投影峰值比。

    NCC 衡量形状相似度但对笔画粗细不敏感（均值归一化消去了亮度差异）。
    字形指纹补充密度信息：宋体笔画密度通常显著高于仿宋，即使 NCC 通过，
    密度差异 >50% 也应警告用户复核。

    返回 dict:
      density     - 暗像素 / 外接框面积 (0~1)
      h_v_ratio   - 水平投影峰值 / 垂直投影峰值；接近 1 表示横竖均衡（如黑体），
                    <1 表示竖画比横画粗（宋体/仿宋常见）
    """
    m = gray < thr
    h, w = gray.shape
    total = h * w
    if total == 0 or not m.any():
        return {"density": 0.0, "h_v_ratio": 0.0}
    dark = int(m.sum())
    h_proj = m.sum(axis=1)   # 每行的暗像素数
    v_proj = m.sum(axis=0)   # 每列的暗像素数
    h_peak = int(h_proj.max())
    v_peak = int(v_proj.max())
    h_v_ratio = h_peak / v_peak if v_peak > 0 else 0.0
    return {"density": dark / total, "h_v_ratio": h_v_ratio}


def rendered_fingerprint(char, font_path, idx, size=36):
    """渲染指定字体的字形并返回其指纹。"""
    g = render_glyph(char, font_path, idx, size)
    if g is None:
        return None
    return glyph_fingerprint(g)


def parse_ref(s, image_size=None):
    """char=x1,y1,x2,y2 -> (char, (x1,y1,x2,y2))

    image_size=(W,H) 给出时，额外校验框完整落在图像内（BUG-061）——
    越界框在 numpy 切片中会被静默截小，导致墨迹尺寸/密度计算偏移。
    """
    # BUG-046：坐标个数错时旧实现 `x1,y1,x2,y2 = (...)` 直接 ValueError 裸 traceback。
    if '=' not in s:
        raise SystemExit(f"错误: --ref 格式应为 字符=x1,y1,x2,y2，收到: {s!r}")
    name, coords = s.split('=', 1)
    parts = [v.strip() for v in coords.split(',')]
    if len(parts) != 4:
        raise SystemExit(
            f"错误: --ref 坐标需为 4 个值 x1,y1,x2,y2，收到 {len(parts)} 个: {coords!r}"
        )
    try:
        x1, y1, x2, y2 = (int(v) for v in parts)
    except ValueError:
        raise SystemExit(f"错误: --ref 坐标需为整数，收到: {coords!r}")
    # BUG-037：负坐标会静默回绕，与 scan_edit_ops.parse_box 一致地拒绝。
    if x1 < 0 or y1 < 0 or x2 < 0 or y2 < 0:
        raise SystemExit(f"错误: --ref 坐标需全部非负，收到: {coords!r}")
    if x1 >= x2 or y1 >= y2:
        raise SystemExit(f"错误: --ref 坐标需满足 x1<x2 且 y1<y2，收到: {coords!r}")
    if image_size is not None:
        img_w, img_h = image_size
        if x2 > img_w or y2 > img_h:
            raise SystemExit(
                f"错误: --ref {s!r} 坐标越出图像边界 {img_w}×{img_h}，"
                "请核对坐标是否为该图像内的像素坐标。"
            )
    return name.strip(), (x1, y1, x2, y2)


def main():
    ap = argparse.ArgumentParser(description='识别扫描件原文字体（灰度 NCC + 高度归一化 + 多字聚合）')
    ap.add_argument('--source', required=True, help='源扫描图 (PNG)')
    ap.add_argument('--ref', action='append', required=True, metavar='CHAR=X1,Y1,X2,Y2',
                    help='参考字及其框，可多次给出（推荐 2~4 个不同结构的字）')
    ap.add_argument('--candidates', default='',
                    help='逗号分隔覆盖默认候选。格式: 仿宋=simfang.ttf,宋体=simsun.ttc')
    args = ap.parse_args()

    im = Image.open(args.source).convert('L')
    arr = np.asarray(im).astype(np.float32)

    targets = {}
    seen_chars: set[str] = set()
    for spec in args.ref:
        ch, box = parse_ref(spec, image_size=im.size)
        # BUG-046：同一字符名多次给出时旧实现静默覆盖，后面框取代前面框，
        # 用户可能误以为两个框都被采用。无论墨迹是否有效都应显式警告。
        if ch in seen_chars:
            print(f'警告: 参考字 {ch} 重复给出，后一个框 {box} 覆盖前一个。'
                  '若想用多个字，请给不同的字符名。', file=sys.stderr)
        seen_chars.add(ch)
        x1, y1, x2, y2 = box
        g = ink_bbox(arr[y1:y2, x1:x2])
        if g is None:
            print(f'警告: {ch} ({box}) 二值化后无墨迹，跳过。检查框坐标或墨迹阈值。', file=sys.stderr)
            continue
        targets[ch] = g
    if not targets:
        print('错误: 没有可用的参考字', file=sys.stderr)
        sys.exit(1)
    print(f'参考字: {", ".join(targets.keys())}  (高度归一化到 {HN}px)\n')

    if args.candidates:
        # BUG-046：尾逗号（如 "仿宋=x.ttf,"）产生空项，split('=') 值不够解包 → 裸 traceback。
        # 过滤空项并校验每项含 '='。
        cands = {}
        for item in args.candidates.split(','):
            item = item.strip()
            if not item:
                continue
            if '=' not in item:
                print(f'错误: --candidates 每项格式应为 名称=文件名，收到: {item!r}', file=sys.stderr)
                sys.exit(2)
            name, fn = item.split('=', 1)
            cands[name.strip()] = (fn.strip(), 0)
    else:
        cands = CJK_CANDIDATES

    header = f'{"字体":<22}' + ''.join(f'{ch:>8}' for ch in targets) + f'{"合计":>9}'
    print(header)
    print('-' * len(header))

    agg = {}
    uninstalled = []  # [(name, filename)] 收集未安装候选，用于置信度不足时给出安装提示
    for name, (fn, idx) in cands.items():
        path = resolve_font(fn)
        if not path:
            uninstalled.append((name, fn))
            print(f'{name:<22}{"(未安装 "+fn+")":>8}')
            continue
        scores = []
        for ch, tg in targets.items():
            scores.append(best_ncc(tg, path, idx, ch))
        total = sum(scores)
        agg[name] = total
        print(f'{name:<22}' + ''.join(f'{s:>8.3f}' for s in scores) + f'{total:>9.3f}')

    print('-' * len(header))
    if not agg:
        print('未匹配到任何已安装的候选字体。', file=sys.stderr)
        if uninstalled:
            print('本机未安装的候选:', file=sys.stderr)
            for name, fn in uninstalled:
                print(f'  - {name} ({fn})', file=sys.stderr)
        print('安装字体后重跑：macOS 放入 ~/Library/Fonts 或 /Library/Fonts；'
              'Windows 放入 C:\\Windows\\Fonts。', file=sys.stderr)
        sys.exit(1)
    ranked = sorted(agg.items(), key=lambda x: -x[1])
    top_name, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_score - second_score
    # 以"总分 / 字数"作为单字均分判断
    avg = top_score / len(targets)
    # BUG-043：只有一个已装候选时 second_score=0，margin=总分必然达标，均分≥0.6
    # 即误判"确定（明显领先）"——这正是该脚本核心使用场景（只装了目标字体），
    # 且"确定"会抑制下方"目标字体可能未安装"的提示。只有一个候选时不允许判"确定"。
    if len(ranked) < 2:
        verdict = '参考（仅一个已装候选，无法比较领先度，建议安装更多候选字体以交叉验证）'
    elif avg >= 0.6 and margin >= 0.15 * len(targets):
        verdict = '确定（明显领先）'
    elif avg >= 0.5:
        verdict = '参考（领先不足，建议增加参考字或结合文档类型）'
    else:
        verdict = '存疑（NCC 偏低，参考字可能太小/太糊，换更大的字）'
    print(f'=> 最优: {top_name}   均分={avg:.3f}  领先第二名 {margin:.3f}  ({verdict})')

    # ── 密度交叉验证 ──
    # NCC 对笔画粗细不敏感（均值归一化消去了亮度差异），但不同字体的
    # 笔画密度差异很大（如宋体 vs 仿宋可差 2 倍）。即使 NCC 判定"确定"，
    # 若密度差异过大也应警告用户复核。
    # 典型案例: task002 原文为仿宋但本机未安装，Songti SC NCC 最高但每字
    # 暗像素数是原文的 2 倍（205 vs 103），合成字明显偏粗。
    top_fn, top_idx = cands[top_name]
    top_path = resolve_font(top_fn)
    if top_path:
        ref_densities = [glyph_fingerprint(tg)["density"] for tg in targets.values()]
        rend_densities = []
        for ch in targets:
            rfp = rendered_fingerprint(ch, top_path, top_idx)
            if rfp is not None:
                rend_densities.append(rfp["density"])
        if ref_densities and rend_densities and (d_ref := sum(ref_densities) / len(ref_densities)) > 0.01:
            d_rend = sum(rend_densities) / len(rend_densities)
            ratio = d_rend / d_ref
            print()
            print('── 密度交叉验证 ──')
            print(f'扫描件参考字平均密度: {d_ref:.3f}')
            print(f'{top_name} 渲染字平均密度: {d_rend:.3f}')
            print(f'密度比 (渲染/原文): {ratio:.2f}')
            if ratio > 1.5:
                print('⚠ 警告: 渲染字密度偏高（笔画偏粗），即使 NCC 得分最高，'
                      '笔画粗细可能与原文字体不符。')
                print('  典型场景: 原文为仿宋但本机未安装，误判为宋体（宋体笔画更密）。')
                print('  建议: 1) 安装更多候选字体后重跑；'
                      '2) 用 scan_text_fusion 加字后做像素级对比验证。')
            elif ratio < 0.67:
                print('⚠ 警告: 渲染字密度偏低（笔画偏细），即使 NCC 得分最高，'
                      '笔画粗细可能与原文字体不符。')
                print('  建议: 1) 安装更多候选字体后重跑；'
                      '2) 用 scan_text_fusion 加字后做像素级对比验证。')
            else:
                print('密度匹配良好。')

    # 置信度不足且存在未安装候选时，提示可能是目标字体缺失。
    # 典型场景：公文/法律文书正文多为仿宋（simfang.ttf），本机未安装时
    # identify_font 只能在已装字体里挑最高 NCC，常给出"参考/存疑"且合成字偏粗偏黑。
    if '确定' not in verdict and uninstalled:
        print()
        print('提示: 以下候选字体本机未安装，置信度偏低可能因此而来（目标字体缺失，'
              '只能在已装字体里挑最高 NCC）:')
        for name, fn in uninstalled:
            print(f'  - {name} ({fn})')
        print('若原文是公文/法律文书，正文常见仿宋（simfang.ttf）。'
              '安装对应字体后重跑：macOS 放入 ~/Library/Fonts 或 /Library/Fonts；'
              'Windows 放入 C:\\Windows\\Fonts。')


if __name__ == '__main__':
    main()
