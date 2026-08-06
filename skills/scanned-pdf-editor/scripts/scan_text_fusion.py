#!/usr/bin/env python3
"""扫描件加字融合工具（Scan-Text Fusion）

把一段文字加到扫描件图片上，并做扫描质感融合，让新加的文字在颜色、对比、
锯齿、灰度噪点和蓝灰边缘晕染上尽量贴近原扫描字，看上去像扫描件本身的一部
分。全程本地像素合成，不做生成式重绘，且每轮只改动新增文字区域。

最终成图管线（已验证）：

    源图 ──▶ 扫描融合修复(render_scan_fusion) ──▶ 蓝灰边缘晕染(render_halo) ──▶ 最终

两个核心渲染函数的数学来自 20260730 项目多轮迭代验证的结果，本脚本只是把
当时硬编码的「文字内容 / 坐标 / 字体 / 颜色」抽成参数，默认值即当时定稿值。

典型用法：

    # 1) 先取样参考文字颜色（框选原扫描里一行字）
    python3 scan_text_fusion.py --source page.png \\
        --sample-only 315 788 675 835

    # 2) 加字融合（用上一步得到的颜色）
    python3 scan_text_fusion.py --source page.png \\
        --text "（实习律师）" --position 445 735 \\
        --ink-color 90 97 106 \\
        --crop-box 150 700 820 850
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import font_registry


# ───────────────────────────── 默认值（即 20260730 定稿参数）─────────────────────────────
# 字体默认值不再硬编码某平台路径——运行时由 font_registry 解析本机首个可用 CJK 字体。
# 真实任务务必先跑 identify_font.py 识别原文字体，再用 --font 覆盖（见 SKILL 第 2 步）。
DEFAULT_FONT_PATH = None        # None = 运行时解析（font_registry.default_cjk_font）
DEFAULT_FONT_INDEX = 0
DEFAULT_FONT_SIZE = 31
DEFAULT_INK_COLOR = (90, 97, 106)        # 笔画主体深灰蓝
DEFAULT_HALO_COLOR = (178, 196, 211)     # 边缘极淡蓝灰
DEFAULT_SEED = 20260701         # 该 seed 经推导可 bit-exact 复现定稿图的融合数学
DEFAULT_FUSION_STRENGTH = 1.0   # 1.0 = 定稿强度（粗糙扫描）；干净扫描建议 0.3~0.5
DEFAULT_HALO_STRENGTH = 1.0

# 字重肩部与核心透明度缩放——来自删除项目 replace_shengsu_with_jiean.py 的收敛结果。
# 默认关闭（0.0 / 0.965），保持增加文字路线的 bit-exact 复现。
# 替换后备路径（模式 C-2）应通过参数开启，否则合成字会"细、硬、黑"。
DEFAULT_STROKE_SHOULDER_BLEND = 0.0    # 0.0 = 关闭；替换后备建议 0.25
DEFAULT_CORE_ALPHA_SCALE = 0.965       # 增加文字默认；替换后备建议 0.875

# 扫描风格预设：影响"--fusion-strength 缺省值"与"--variants 对比图的强度档位"。
# clean = 干净扫描（少噪，fusion 低档）；rough = 粗糙扫描（定稿强度）。
SCAN_STYLE_DEFAULTS = {
    "clean": {"fusion": 0.4, "variants": [0.25, 0.35, 0.5]},
    "rough": {"fusion": 1.0, "variants": [0.85, 1.0, 1.15]},
}


# ───────────────────────────── 基础工具 ─────────────────────────────
def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def load_font(path: str | Path | None = DEFAULT_FONT_PATH, size: int = DEFAULT_FONT_SIZE,
              index: int = DEFAULT_FONT_INDEX) -> ImageFont.FreeTypeFont:
    if path is None:
        resolved = font_registry.default_cjk_font()
        if resolved is None:
            raise FileNotFoundError(
                "未找到任何 CJK 字体。请用 --font 指定，或先跑 identify_font.py 识别原文字体。")
        path, index = resolved
    return ImageFont.truetype(str(path), size, index=index)


def make_text_mask(size: tuple[int, int], font: ImageFont.FreeTypeFont,
                   position: tuple[int, int], text: str,
                   *, stroke_shoulder_blend: float = DEFAULT_STROKE_SHOULDER_BLEND) -> Image.Image:
    """渲染文字到一个 L 通道 mask（255=笔画）。所有融合计算都基于这个 mask。

    stroke_shoulder_blend > 0 时，对 mask 做 3×3 MaxFilter 扩张后以该权重混回，
    模拟扫描字的亚像素中灰肩部。用于替换后备路径（模式 C-2）防止"细、硬、黑"。
    """
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).text(position, text, font=font, fill=255)
    if stroke_shoulder_blend > 0:
        expanded = mask.filter(ImageFilter.MaxFilter(3))
        mask = Image.blend(mask, expanded, stroke_shoulder_blend)
    return mask


def smooth_noise(shape: tuple[int, int], rng: np.random.Generator,
                 blur: float, amp: float) -> np.ndarray:
    """生成平滑的 [-amp/2, amp/2] 浮点噪声场，用于模拟墨色/alpha 的不均匀。

    1×1 等退化形状时 noise.max()==noise.min()，归一化除零产生 NaN（BUG-031）；
    此时无噪声变异可言，返回零场。
    """
    noise = rng.normal(0, 1, shape).astype(np.float32)
    span = float(noise.max() - noise.min())
    if span == 0.0:
        return np.zeros(shape, dtype=np.float32)
    noise = (noise - noise.min()) / span
    img = Image.fromarray(np.uint8(noise * 255), "L").filter(ImageFilter.GaussianBlur(blur))
    return (np.asarray(img).astype(np.float32) / 255.0 - 0.5) * amp


def derive_seeds(seed: int) -> dict[str, int]:
    """由单一 --seed 推导各阶段随机种子。

    seed=20260701（默认）时：
      fusion 主种子 = 2026070102、halo 主种子 = 2026070117，
    恰好等于定稿脚本里写死的值，因此默认参数可 bit-exact 复现定稿图。
    """
    return {
        "fusion": seed * 100 + 2,
        "fusion_smooth_a": seed * 100 + 2 + 11,
        "fusion_smooth_b": seed * 100 + 2 + 23,
        "halo": seed * 100 + 17,
    }


# ───────────────────────────── 核心渲染：干净加字（用于核对位置）─────────────────────────────
def render_clean_text(base: Image.Image, *, text: str, position: tuple[int, int],
                      font: ImageFont.FreeTypeFont, color: tuple[int, int, int],
                      alpha: int = 252, blur: float = 0.16) -> Image.Image:
    """只叠加一层干净文字，不做扫描质感。用于先确认位置/字号/字体是否合适。"""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(position, text, font=font, fill=color + (alpha,))
    r, g, b, a = layer.split()
    a = a.filter(ImageFilter.GaussianBlur(blur))
    softened = Image.merge("RGBA", (r, g, b, a))
    return Image.alpha_composite(base.convert("RGBA"), softened).convert("RGB")


# ───────────────────────────── 核心渲染：扫描融合修复（笔画主体）─────────────────────────────
def render_scan_fusion(base: Image.Image, *, text: str, position: tuple[int, int],
                       font: ImageFont.FreeTypeFont, ink_color: Sequence[int],
                       seed: int = DEFAULT_SEED, strength: float = DEFAULT_FUSION_STRENGTH,
                       stroke_shoulder_blend: float = DEFAULT_STROKE_SHOULDER_BLEND,
                       core_alpha_scale: float = DEFAULT_CORE_ALPHA_SCALE) -> Image.Image:
    """扫描融合修复：把干净文字处理成有扫描扩散、灰度起伏、轻微断裂、边缘毛刺的笔画。

    strength=1.0 为定稿强度；增大->更粗糙/更虚，减小->更干净/更实。

    stroke_shoulder_blend / core_alpha_scale 用于替换后备路径（模式 C-2）的字重匹配：
    - stroke_shoulder_blend=0.25：3×3 MaxFilter 扩张轮廓后以 0.25 权重混回，增加中灰肩部
    - core_alpha_scale=0.875：降低死黑核心比例，让新增面积主要出现在中灰边缘
    增加文字路线（模式 D）保持默认值（0.0 / 0.965）以 bit-exact 复现定稿图。
    """
    seeds = derive_seeds(seed)
    mask = make_text_mask(base.size, font, position, text, stroke_shoulder_blend=stroke_shoulder_blend)
    mask_arr = np.asarray(mask).astype(np.float32) / 255.0
    alpha_soft = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.34))).astype(np.float32) / 255.0
    alpha_halo = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.72))).astype(np.float32) / 255.0
    edge_band = (alpha_halo > 0.018) & (alpha_soft < 0.93)
    core_band = mask_arr > 0.55
    rng = np.random.default_rng(seeds["fusion"])
    s = float(strength)

    alpha = np.power(np.clip(alpha_soft, 0, 1), 0.86)
    alpha *= core_alpha_scale
    alpha += smooth_noise(alpha.shape, np.random.default_rng(seeds["fusion_smooth_a"]), 1.15, 0.18) * alpha * 0.45
    alpha += rng.normal(0, 0.030 * s, alpha.shape).astype(np.float32) * (alpha > 0.35)
    alpha = np.maximum(alpha, alpha_halo * 0.37)
    alpha[edge_band] += rng.normal(0, 0.070 * s, alpha.shape).astype(np.float32)[edge_band]

    drop = rng.random(alpha.shape)
    low_drop = 0.015 * s
    low_mask = edge_band & (drop < low_drop)
    high_mask = edge_band & (drop > 0.986)
    # 注意：即使掩码为空也要调用 rng.uniform，以保持与定稿脚本一致的 RNG 调用次序
    alpha[low_mask] *= rng.uniform(0.42, 0.78, low_mask.sum())
    alpha[high_mask] = np.clip(alpha[high_mask] * 1.16 + 0.035, 0, 1)
    holes = (rng.random(alpha.shape) < 0.006 * s) & core_band
    alpha[holes] *= rng.uniform(0.72, 0.90, holes.sum())

    alpha_q = np.round(np.clip(alpha, 0, 1) * 15) / 15
    alpha_img = Image.fromarray(np.uint8(np.clip(alpha_q * 255, 0, 255)), "L").filter(ImageFilter.GaussianBlur(0.06))
    alpha = np.asarray(alpha_img).astype(np.float32) / 255.0

    rgb = np.asarray(base).astype(np.float32)
    ink_base = np.asarray(ink_color, dtype=np.float32)
    ink_noise = smooth_noise(alpha.shape, np.random.default_rng(seeds["fusion_smooth_b"]), 0.50, 9.0 * s)
    ink_noise += rng.normal(0, 1.1 * s, alpha.shape).astype(np.float32)
    ink = np.zeros_like(rgb)
    for ch in range(3):
        ink[:, :, ch] = np.clip(ink_base[ch] + ink_noise, 0, 255)
    out = rgb * (1 - alpha[..., None]) + ink * alpha[..., None]
    return Image.fromarray(np.uint8(np.clip(out, 0, 255)))

# ───────────────────────────── 核心渲染：蓝灰边缘晕染/底噪 ─────────────────────────────
def render_halo(base_with_text: Image.Image, *, text: str, position: tuple[int, int],
                font: ImageFont.FreeTypeFont, halo_color: Sequence[int],
                seed: int = DEFAULT_SEED, strength: float = DEFAULT_HALO_STRENGTH,
                stroke_shoulder_blend: float = DEFAULT_STROKE_SHOULDER_BLEND) -> Image.Image:
    """在笔画外缘加极淡蓝灰扩散，模拟扫描的综合色偏/插值/纸张底色/边缘色散。

    只作用在笔画外侧，主体不变蓝；strength=1.0 时最高透明度约 10%、平均约 3%~4%。
    stroke_shoulder_blend 应与 render_scan_fusion 保持一致，确保 mask 相同。
    """
    seeds = derive_seeds(seed)
    mask = make_text_mask(base_with_text.size, font, position, text, stroke_shoulder_blend=stroke_shoulder_blend)
    core = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.24))).astype(np.float32) / 255.0
    outer = np.asarray(mask.filter(ImageFilter.GaussianBlur(1.55))).astype(np.float32) / 255.0
    wide = np.asarray(mask.filter(ImageFilter.GaussianBlur(2.35))).astype(np.float32) / 255.0
    halo = np.clip((outer - core * 0.58) * 1.18 + wide * 0.13, 0, 1)
    halo *= np.clip(1.0 - core * 0.88, 0, 1)

    rng = np.random.default_rng(seeds["halo"])
    low = rng.normal(0, 1, halo.shape).astype(np.float32)
    low = (low - low.min()) / (low.max() - low.min())
    low_img = Image.fromarray(np.uint8(low * 255), "L").filter(ImageFilter.GaussianBlur(0.95))
    low = np.asarray(low_img).astype(np.float32) / 255.0
    fine = rng.normal(0, 0.22, halo.shape).astype(np.float32)
    texture = np.clip(0.72 + low * 0.48 + fine, 0.28, 1.35)
    drop = rng.random(halo.shape)
    low_mask = drop < 0.018
    high_mask = drop > 0.988
    # 注意：即使掩码为空也要调用 rng.uniform，以保持与定稿脚本一致的 RNG 调用次序
    texture[low_mask] *= rng.uniform(0.25, 0.70, low_mask.sum())
    texture[high_mask] *= rng.uniform(1.08, 1.35, high_mask.sum())

    gain = 0.118 * float(strength)
    cap = min(0.105 * float(strength), 0.20)
    alpha = np.clip(halo * texture * gain, 0, cap)
    alpha[wide < 0.006] = 0

    rgb = np.asarray(base_with_text).astype(np.float32)
    color_base = np.asarray(halo_color, dtype=np.float32)
    color_noise = (low - 0.5) * 12 + rng.normal(0, 1.2, halo.shape).astype(np.float32)
    halo_rgb = np.zeros_like(rgb)
    for ch in range(3):
        halo_rgb[:, :, ch] = np.clip(color_base[ch] + color_noise, 0, 255)
    out = rgb * (1 - alpha[..., None]) + halo_rgb * alpha[..., None]
    return Image.fromarray(np.uint8(np.clip(out, 0, 255)))


# ───────────────────────────── 参考颜色取样 ─────────────────────────────
def sample_ink_color(image: Image.Image, box: tuple[int, int, int, int],
                     quiet: bool = False) -> tuple[int, int, int]:
    """从参考区域取样「深色主体」颜色。

    思路：框选一段原扫描文字，按亮度逐级收紧阈值，取最暗一批像素的颜色中位数，
    作为新增文字的笔画主体色。返回 (R, G, B)。
    """
    x1, y1, x2, y2 = box
    arr = np.asarray(image.convert("RGB"))[y1:y2, x1:x2]
    # BUG-025：框在图外/宽高为 0 时切片为空，后续 np.median 得 NaN 再转 int 崩溃。
    # 空 ROI 直接报清晰错误，提示框与图像尺寸。
    if arr.size == 0:
        raise ValueError(
            f"参考框 {box} 与图像没有交集（图像尺寸 {image.size}），无法取样墨色。"
            "请检查坐标是否为像素坐标、是否写反或越界。"
        )
    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    chosen = None
    if not quiet:
        print(f"reference ROI: {box}")
    for threshold in [180, 165, 150, 135, 120, 105]:
        mask = luma < threshold
        if mask.sum():
            colors = arr[mask]
            median = np.median(colors, axis=0)
            mean = colors.mean(axis=0)
            if not quiet:
                print(f"  threshold<{threshold}: n={int(mask.sum())} "
                      f"median={np.round(median, 1)} mean={np.round(mean, 1)}")
            chosen = tuple(int(round(v)) for v in median)
    if chosen is None:
        # 区域里没有明显深色像素，退回整体中位数
        chosen = tuple(int(round(v)) for v in np.median(arr.reshape(-1, 3), axis=0))
        if not quiet:
            print(f"  no dark pixels found, fallback to ROI median: {chosen}")
    return chosen


# ───────────────────────────── 输出辅助 ─────────────────────────────
def auto_crop_box(position: tuple[int, int], image_size: tuple[int, int],
                  text: str, font_size: int) -> tuple[int, int, int, int]:
    """未显式给 crop-box 时，根据位置和字号估一个预览框。"""
    x, y = position
    # 中文粗体大致每字宽 ≈ 字号；估文字宽度
    est_width = max(len(text) * font_size, 200)
    pad_x, pad_y = 60, 50
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(image_size[0], x + est_width + pad_x)
    y2 = min(image_size[1], y + int(font_size * 2.4) + pad_y)
    return (x1, y1, x2, y2)


def labeled_compare(panels: list[tuple[str, Image.Image]], output_path: Path,
                    label_font_path: str | None = None) -> Path:
    """把若干 (标签, 图) 纵向拼成一张对比图。"""
    ensure_dir(output_path.parent)
    if label_font_path is None:
        dj = font_registry.default_cjk_font()
        label_font_path = dj[0] if dj else None
    if label_font_path is not None:
        label_font = load_font(label_font_path, 18, index=0)
    else:
        label_font = ImageFont.load_default()
    width = max(img.width for _, img in panels)
    rendered = []
    for label, img in panels:
        panel = Image.new("RGB", (width, img.height + 34), "white")
        panel.paste(img.convert("RGB"), (0, 34))
        ImageDraw.Draw(panel).text((8, 6), label, font=label_font, fill=(55, 55, 55))
        rendered.append(panel)
    gap = 10
    canvas = Image.new("RGB", (width, sum(p.height for p in rendered) + gap * (len(rendered) - 1)), "white")
    y = 0
    for panel in rendered:
        canvas.paste(panel, (0, y))
        y += panel.height + gap
    canvas.save(output_path)
    return output_path


def save_with_crop(image: Image.Image, output_dir: Path, filename: str,
                   crop_box: tuple[int, int, int, int] | None,
                   crop_filename: str | None = None) -> Path:
    full = output_dir / filename
    # BUG-025：--output 允许含子目录成分（如 sub/x.png），只建 output_dir 会
    # FileNotFoundError；按完整目标路径建父目录。
    ensure_dir(full.parent)
    image.save(full, quality=95)
    if crop_box and crop_filename:
        image.crop(crop_box).save(output_dir / crop_filename)
    return full


# ───────────────────────────── 主流程 ─────────────────────────────
def run(args: argparse.Namespace) -> dict[str, Path]:
    source = Path(args.source)
    if not source.exists():
        raise FileNotFoundError(f"Source image not found: {source}")
    base = load_rgb(source)
    output_dir = ensure_dir(Path(args.output_dir))

    # 字体：--font 优先（路径用用户索引，注册名用注册表索引）；缺省由注册表解析
    if args.font:
        if os.path.exists(args.font):
            font_path, font_index = args.font, args.font_index
        else:
            resolved = font_registry.find_font(args.font)
            if resolved is None:
                raise FileNotFoundError(
                    f"找不到字体 {args.font!r}。请用 identify_font.py 识别后给出正确 --font。")
            font_path, font_index = resolved
    else:
        font_path, font_index = font_registry.require_default_font()
    font = load_font(font_path, args.font_size, index=font_index)

    # 颜色：参考框取样 > 显式 ink-color > 默认
    if args.reference_box:
        ink_color = sample_ink_color(base, tuple(args.reference_box), quiet=False)
        print(f"sampled ink color: {ink_color}")
    else:
        ink_color = tuple(args.ink_color)

    halo_color = tuple(args.halo_color)

    # crop 框
    crop_box = tuple(args.crop_box) if args.crop_box else auto_crop_box(
        tuple(args.position), base.size, args.text, args.font_size)

    stem = source.stem
    outputs: dict[str, Path] = {}

    stage = args.stage
    produce_clean = stage in ("clean", "all")
    produce_fusion = stage in ("fusion", "halo", "all")
    produce_halo = stage in ("halo", "all")

    if produce_clean:
        clean = render_clean_text(base, text=args.text, position=tuple(args.position),
                                  font=font, color=ink_color)
        outputs["clean"] = save_with_crop(
            clean, output_dir, f"{stem}_clean.png", crop_box, f"{stem}_clean_crop.png")

    if produce_fusion or produce_halo:
        fusion = render_scan_fusion(base, text=args.text, position=tuple(args.position),
                                    font=font, ink_color=ink_color,
                                    seed=args.seed, strength=args.fusion_strength,
                                    stroke_shoulder_blend=args.stroke_shoulder,
                                    core_alpha_scale=args.core_alpha_scale)
        if produce_fusion:
            outputs["fusion"] = save_with_crop(
                fusion, output_dir, f"{stem}_fusion.png", crop_box, f"{stem}_fusion_crop.png")

    if produce_halo:
        final = render_halo(fusion, text=args.text, position=tuple(args.position),
                            font=font, halo_color=halo_color,
                            seed=args.seed, strength=args.halo_strength,
                            stroke_shoulder_blend=args.stroke_shoulder)
        main_name = args.output or f"{stem}_text_fused.png"
        outputs["final"] = save_with_crop(
            final, output_dir, main_name, crop_box,
            (Path(main_name).stem + "_crop.png"))

    # 变体对比接触图：按 --fusion-variants / --scan-style 给的强度档，每档渲染 fusion+halo。
    # 若给了 --reference-box，首格放原扫描参考字裁剪，便于人眼直接对比"噪点/毛刺"是否一致。
    if args.variants:
        if args.fusion_variants:
            strengths = [float(x) for x in args.fusion_variants.split(",")]
        else:
            strengths = SCAN_STYLE_DEFAULTS[args.scan_style]["variants"]
        panels: list[tuple[str, Image.Image]] = []
        if args.reference_box:
            panels.append(("scan 参考（原扫描字）", base.crop(tuple(args.reference_box))))
        for s in strengths:
            var_fu = render_scan_fusion(base, text=args.text, position=tuple(args.position),
                                        font=font, ink_color=ink_color, seed=args.seed, strength=s,
                                        stroke_shoulder_blend=args.stroke_shoulder,
                                        core_alpha_scale=args.core_alpha_scale)
            var = render_halo(var_fu, text=args.text, position=tuple(args.position),
                              font=font, halo_color=halo_color,
                              seed=args.seed, strength=args.halo_strength,
                              stroke_shoulder_blend=args.stroke_shoulder)
            panels.append((f"fusion {s:g} + halo {args.halo_strength:g}", var.crop(crop_box)))
        outputs["variants_compare"] = labeled_compare(panels, output_dir / f"{stem}_fusion_variants.png")

    # 上下对比：原图裁剪 vs 最终裁剪
    if args.compare and produce_halo:
        outputs["before_after"] = labeled_compare(
            [("原图", base.crop(crop_box)), ("加字融合", final.crop(crop_box))],
            output_dir / f"{stem}_before_after.png")

    return outputs


# ───────────────────────────── CLI ─────────────────────────────
def triad(s: str) -> tuple[int, ...]:
    parts = s.replace(",", " ").split()
    return tuple(int(p) for p in parts)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="扫描件加字融合：把文字加到扫描件上并做扫描质感融合。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="默认复现 20260730 定稿的融合数学；字体需按 identify_font.py 识别结果用 --font 指定。",
    )
    p.add_argument("--source", type=Path, required=True, help="源扫描图片路径")
    p.add_argument("--text", default="（实习律师）", help="要加的文字（默认：（实习律师））")
    p.add_argument("--position", nargs=2, metavar=("X", "Y"), type=int, default=None,
                   help="文字左上角坐标 X Y（像素）；仅 --sample-only 模式可省略")
    p.add_argument("--font", default=None,
                   help="字体路径/注册名(如 仿宋)/文件名；缺省=本机首个可用 CJK 字体（先跑 identify_font.py）")
    p.add_argument("--font-index", type=int, default=DEFAULT_FONT_INDEX, help="ttc 字体索引（默认 0）")
    p.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE, help="字号（默认 31；用 identify_size.py 定）")
    p.add_argument("--ink-color", type=int, nargs=3, metavar=("R", "G", "B"),
                   default=list(DEFAULT_INK_COLOR), help="笔画主体颜色（默认 90 97 106）")
    p.add_argument("--reference-box", type=int, nargs=4, metavar=("X1", "Y1", "X2", "Y2"),
                   help="框选原扫描参考文字：自动取样 ink 颜色，并作为 --variants 接触图的 scan 参考格")
    p.add_argument("--halo-color", type=int, nargs=3, metavar=("R", "G", "B"),
                   default=list(DEFAULT_HALO_COLOR), help="边缘晕染颜色（默认 178 196 211）")
    p.add_argument("--crop-box", type=int, nargs=4, metavar=("X1", "Y1", "X2", "Y2"),
                   help="预览裁剪框（不给则按 position 自动估）")
    p.add_argument("--stage", choices=["clean", "fusion", "halo", "all"], default="halo",
                   help="产出阶段：clean=仅干净加字；fusion=仅融合；halo=融合+晕染（默认）；all=全产出+对比")
    p.add_argument("--variants", action="store_true",
                   help="生成融合强度对比接触图（首格为 scan 参考字，需配合 --reference-box）")
    p.add_argument("--fusion-variants", metavar="LIST",
                   help="自定义 --variants 的强度档，逗号分隔，如 0.25,0.35,0.5（不给则按 --scan-style）")
    p.add_argument("--scan-style", choices=["clean", "rough"], default="rough",
                   help="扫描风格预设：clean=干净扫描(fusion 0.4/低档)；rough=粗糙扫描(fusion 1.0/定稿，默认)")
    p.add_argument("--compare", action="store_true", help="额外生成 原图 vs 最终 的前后对比图")
    p.add_argument("--fusion-strength", type=float, default=None,
                   help="融合粗糙度倍率；不给则按 --scan-style（rough→1.0=定稿，clean→0.4）。干净扫描建议 0.3~0.5")
    p.add_argument("--halo-strength", type=float, default=DEFAULT_HALO_STRENGTH,
                   help="蓝灰晕染强度倍率（默认 1.0=定稿；建议 0.7~1.3）")
    p.add_argument("--stroke-shoulder", type=float, default=DEFAULT_STROKE_SHOULDER_BLEND,
                   help="字重肩部混合权重（默认 0.0=关闭；替换后备 C-2 建议 0.25）")
    p.add_argument("--core-alpha-scale", type=float, default=DEFAULT_CORE_ALPHA_SCALE,
                   help="核心透明度缩放（默认 0.965=增加文字；替换后备 C-2 建议 0.875）")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子（默认 20260701=复现定稿）")
    p.add_argument("--output-dir", type=Path, default=Path("./scan_text_fusion_out"), help="输出目录")
    p.add_argument(
        "--output",
        help="最终文件名（相对 --output-dir 内的文件名，不是完整路径；默认 <源名>_text_fused.png）",
    )

    # 诊断模式：只取样颜色
    p.add_argument("--sample-only", type=int, nargs=4, metavar=("X1", "Y1", "X2", "Y2"),
                   help="只对参考框取样并打印颜色统计后退出（不生成图）")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.sample_only:
        source = Path(args.source)
        if not source.exists():
            raise FileNotFoundError(f"Source image not found: {source}")
        sample_ink_color(load_rgb(source), tuple(args.sample_only), quiet=False)
        return 0

    # --sample-only 已 return；其余模式都需要 --position
    if args.position is None:
        parser.error("--position X Y 为必填（仅 --sample-only 诊断模式可省略）")

    # --fusion-strength 缺省 = 按 --scan-style 解析（消除"文档说 0.3~0.5、默认却 1.0"的冲突）
    if args.fusion_strength is None:
        args.fusion_strength = SCAN_STYLE_DEFAULTS[args.scan_style]["fusion"]

    outputs = run(args)
    print(f"source: {args.source}")
    print(f"output_dir: {args.output_dir}")
    for key, path in outputs.items():
        print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
