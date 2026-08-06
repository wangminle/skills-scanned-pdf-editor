"""扫描型 PDF 局部编辑的共用工具。

整合自两个项目的共用函数：
- 删除项目（20260720-P图删除一行内容）的 scan_edit_utils.py
- 供体归一化逻辑（来自 replace_with_donor_jiean.py / process_agreement3.py）
- 行间插值填底（来自 process_chongqing_redline_cleanup.py）

坐标统一使用页面 PNG 的左上角像素坐标，矩形遵循
``(x1, y1, x2, y2)``，右、下边界不包含在内。
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import font_registry


Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class DiffStats:
    changed_pixels: int
    bbox: Box | None


# ───────────────────────────── PDF 渲染与封装 ─────────────────────────────


def render_pdf_page(
    pdf_path: Path,
    output_path: Path | None = None,
    *,
    page_index: int = 0,
    dpi: int = 300,
) -> Image.Image:
    """使用 PDFium 稳定回渲单页；300 dpi 基准图均由此方式得到。"""
    document = pdfium.PdfDocument(str(pdf_path))
    if not 0 <= page_index < len(document):
        raise IndexError(f"页码越界: {page_index + 1}/{len(document)}")
    image = document[page_index].render(scale=dpi / 72).to_pil().convert("RGB")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, dpi=(dpi, dpi))
    return image


def pdf_page_info(pdf_path: Path) -> tuple[int, tuple[float, float]]:
    """返回 (页数, 第一页的点尺寸)。"""
    document = pdfium.PdfDocument(str(pdf_path))
    if not len(document):
        raise ValueError(f"PDF 没有页面: {pdf_path}")
    return len(document), tuple(float(value) for value in document[0].get_size())


def save_image_as_pdf(
    image: Image.Image,
    output_path: Path,
    *,
    page_size: tuple[float, float],
    title: str,
    subject: str,
) -> None:
    """按原页面点尺寸封装整页图，避免按 A4 常量误改非标准扫描页。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = page_size
    pdf = canvas.Canvas(str(output_path), pagesize=page_size)
    pdf.setTitle(title)
    pdf.setSubject(subject)
    pdf.drawImage(
        ImageReader(image),
        0,
        0,
        width=width,
        height=height,
        preserveAspectRatio=False,
        mask="auto",
    )
    pdf.showPage()
    pdf.save()


def replace_pdf_image(
    pdf_path: Path,
    output_path: Path,
    image: Image.Image,
    *,
    page_index: int = 0,
    strict: bool = True,
) -> None:
    """用 PyMuPDF 替换 PDF 内嵌图，保留 OCR 文字层。

    适用于扫描件 PDF（每页仅含一张整页图像 XObject）。

    多图安全：页面含多张图时（logo、印章、背景图等），不再无条件替换
    ``images[0]``。按各图在页面上的覆盖面积比例（bbox 面积 / 页面面积）评分，
    选覆盖比例最大（最接近整页扫描图）的那个 XObject 替换；其余较小图保留。
    ``strict=True`` 时，若多个候选覆盖比例接近（差距 < 0.1 且均较高），认为存在
    替换错对象的风险，报错让调用方人工确认页面结构而非静默替换错内容。
    """
    import fitz

    document = fitz.open(str(pdf_path))
    page = document[page_index]
    images = page.get_images(full=True)
    if not images:
        raise RuntimeError("页面中没有可替换的内嵌图像。")

    xref = _select_page_image_xref(page, images, strict=strict)

    # 与 save_image_as_pdf 行为一致：替换内嵌图模式同样自动创建输出父目录，
    # 否则写入尚未创建的嵌套目录时报 FzErrorSystem: No such file or directory。
    output_path.parent.mkdir(parents=True, exist_ok=True)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    page.replace_image(xref, stream=buffer.getvalue())
    temporary = output_path.with_suffix(".tmp.pdf")
    document.save(str(temporary), garbage=4, deflate=True)
    document.close()
    temporary.replace(output_path)


def _select_page_image_xref(page, images: list, *, strict: bool = True) -> int:
    """从页面内嵌图列表中选出整页扫描图对应的 xref。

    评分 = 该图在页面上的 bbox 面积 / 页面面积。覆盖比例最大的视为整页扫描图。
    单图直接返回；多图按覆盖比例选最大，``strict`` 下若头部并列会报错。
    """
    if len(images) == 1:
        return images[0][0]

    page_rect = page.rect
    page_area = float(page_rect.width * page_rect.height) or 1.0

    scored = []
    for entry in images:
        xref = entry[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []
        area = sum(float(r.width * r.height) for r in rects)
        ratio = area / page_area
        scored.append((xref, ratio))

    scored.sort(key=lambda item: item[1], reverse=True)
    best_xref, best_ratio = scored[0]
    second_ratio = scored[1][1] if len(scored) > 1 else 0.0

    if strict:
        # 头部两个候选覆盖比例都很高且接近时，无法可靠区分整页图与背景图，
        # 静默替换会冒替换错对象的风险——报错让调用方用新建 PDF 模式或人工处理。
        if best_ratio > 0.5 and best_ratio - second_ratio < 0.1:
            raise RuntimeError(
                f"页面含 {len(images)} 张图，覆盖比例最高的两个过近（"
                f"{best_ratio:.2f} vs {second_ratio:.2f}），无法可靠选出整页扫描图。"
                "请改用 package 新建 PDF 模式，或先确认页面结构。"
            )
    return best_xref


# ───────────────────────────── 基础像素工具 ─────────────────────────────


def luma(rgb: np.ndarray) -> np.ndarray:
    """RGB -> 亮度（灰度）。"""
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def feather_mask(width: int, height: int, edge: int = 4) -> np.ndarray:
    """生成边缘羽化的 alpha 蒙版，用于供体贴入时平滑过渡。"""
    yy, xx = np.mgrid[0:height, 0:width]
    distance = np.minimum.reduce((xx, width - 1 - xx, yy, height - 1 - yy)).astype(
        np.float32
    )
    return np.clip(distance / edge, 0, 1)[..., None]


def dark_median(rgb: np.ndarray, threshold: float = 180) -> np.ndarray:
    """取暗色像素（亮度 < threshold）的 RGB 中位数，用于墨迹色采样。"""
    values = rgb[luma(rgb) < threshold]
    if len(values) == 0:
        raise ValueError("参考框中未找到暗色墨迹")
    return np.median(values, axis=0)


def background_median(rgb: np.ndarray, threshold: float = 235) -> np.ndarray:
    """取亮色像素（亮度 > threshold）的 RGB 中位数，用于纸白采样。"""
    values = rgb[luma(rgb) > threshold]
    if len(values) == 0:
        return np.median(rgb.reshape(-1, 3), axis=0)
    return np.median(values, axis=0)


# ───────────────────────────── 删除：墨迹蒙版 + Telea 修补 ─────────────────────────────


def ink_mask_in_boxes(
    image: np.ndarray,
    boxes: Iterable[Box],
    *,
    threshold: int,
    dilation: int = 5,
) -> np.ndarray:
    """只在给定矩形中选取墨迹，避免整块白色覆盖损坏纸张纹理。

    1. 在 boxes 内按亮度阈值提取墨迹
    2. 椭圆膨胀（连接断裂的笔画边缘）

    灰度转换用 cv2 整数灰度（与原项目 cv2.cvtColor 一致），不用浮点 luma：
    两者在阈值边界像素上约有每区域 2k 像素的判定差异，会导致 Telea 修补
    结果与历史基准不一致（复现对比报告 G1）。
    """
    region = np.zeros(image.shape[:2], dtype=np.uint8)
    for x1, y1, x2, y2 in boxes:
        region[y1:y2, x1:x2] = 255
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    mask = np.where((gray < threshold) & (region > 0), 255, 0).astype(np.uint8)
    if dilation > 1:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation, dilation))
        mask = cv2.dilate(mask, kernel, iterations=1)
        # 膨胀会把蒙版扩张到 boxes 外，导致 Telea 修改越过用户框定的区域，
        # 与"目标区外变化为 0"的原则冲突。膨胀后重新与 region 相交，把越界部分裁回。
        mask = cv2.bitwise_and(mask, region)
    return mask


def full_mask_in_boxes(
    image: np.ndarray,
    boxes: Iterable[Box],
) -> np.ndarray:
    """整个矩形区域设为蒙版（不区分墨迹与背景），用于整矩形 Telea 清理。

    原项目 replace_with_donor_jiean.py 的清理方式：把目标框整个区域
    （含背景纸纹）都交给 Telea 重绘，而非只清理墨迹像素。
    适合目标区域背景有扫描残影/污渍需要一并清除的场景（复现对比报告 G2）。
    """
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    for x1, y1, x2, y2 in boxes:
        mask[y1:y2, x1:x2] = 255
    return mask


def inpaint_rgb(image: np.ndarray, mask: np.ndarray, *, radius: int = 5) -> np.ndarray:
    """Telea 修补；保留纸张色差与颗粒，不用纯白矩形覆盖。"""
    repaired = cv2.inpaint(
        cv2.cvtColor(image, cv2.COLOR_RGB2BGR), mask, radius, cv2.INPAINT_TELEA
    )
    return cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB)


def remove_regions_telea(
    image: np.ndarray,
    boxes: Iterable[Box],
    *,
    ink_threshold: int = 180,
    dilation: int = 5,
    inpaint_radius: int = 5,
    mask_mode: str = "ink",
) -> tuple[np.ndarray, np.ndarray]:
    """删除指定区域：墨迹蒙版或整矩形蒙版 + Telea 修补。

    mask_mode:
        ``"ink"`` -- 只清理墨迹像素，保留纸纹（默认，更保守）。
        ``"full"`` -- 整个矩形交给 Telea 重绘，连背景纸纹一并清除
                      （原项目 replace_with_donor_jiean.py 的方式，复现对比 G2）。

    返回 (修补后图像, 蒙版)。
    """
    if mask_mode == "full":
        mask = full_mask_in_boxes(image, boxes)
    else:
        mask = ink_mask_in_boxes(image, boxes, threshold=ink_threshold, dilation=dilation)
    return inpaint_rgb(image, mask, radius=inpaint_radius), mask


# ───────────────────────────── 删除：行间插值填底 ─────────────────────────────


def remove_regions_interpolate(
    image: np.ndarray,
    boxes: Iterable[Box],
    *,
    sample_width: int = 45,
    noise_sigma: float = 0.45,
    seed: int = 20260805,
) -> np.ndarray:
    """删除指定区域：用区域两侧纸张底色逐行插值 + 纵向平滑 + 微噪点。

    适合需要彻底清除文字与扫描残影的场景。
    """
    result = image.copy()
    rng = np.random.default_rng(seed)

    for left, top, right, bottom in boxes:
        h, w = image.shape[:2]
        target_h = bottom - top
        # 裁剪采样范围到图片边界内，防止越界产生空切片 -> NaN -> 黑块
        ls_left = max(left - sample_width, 0)
        ls_right = min(left, w)
        rs_left = max(right, 0)
        rs_right = min(right + sample_width, w)

        left_sample = image[top:bottom, ls_left:ls_right]
        right_sample = image[top:bottom, rs_left:rs_right]
        samples = np.concatenate([left_sample, right_sample], axis=1)

        # 当删除框覆盖整页宽度时，左右样本均为空，改用上下邻域采样
        if samples.shape[1] == 0:
            above_top = max(top - sample_width, 0)
            below_bottom = min(bottom + sample_width, h)
            above = image[above_top:top, left:right]
            below = image[bottom:below_bottom, left:right]
            samples = np.concatenate([above, below], axis=0)
            # 如果上下也空（框 >= 整页），用全图中值填底
            if samples.shape[0] == 0:
                fill_color = np.median(image.reshape(-1, 3), axis=0)
                result[top:bottom, left:right] = fill_color.astype(np.uint8)
                continue

        gray = samples.mean(axis=2)

        row_colors = []
        for row, row_gray in zip(samples, gray):
            paper = row[row_gray > 238]
            if len(paper) == 0:
                paper = row
            row_colors.append(np.median(paper, axis=0))

        row_colors = np.asarray(row_colors, dtype=np.float32)
        # 左右样本天然就是 target_h 行；但整页宽框退化为上下邻域采样时，
        # samples 行数 = 上邻域行数 + 下邻域行数，可能远小于 target_h（如框贴近顶部/底部）。
        # 若不补齐，下面的 range(target_h) 滑动窗口会读到越界的空切片 -> NaN -> 转 uint8 后纯黑。
        # 这里把任意来源的 row_colors 重采样到 target_h，使后续平滑窗口恒定有效。
        if row_colors.shape[0] != target_h:
            # 单行退化（如采样区全暗、只剩一个中值）时直接复制，避免 resize 退化。
            if row_colors.shape[0] == 1:
                row_colors = np.repeat(row_colors, target_h, axis=0)
            else:
                # row_colors 形如 (rows, 3)；当作 (H=rows, W=3) 图线性插值到 (target_h, 3)。
                row_colors = cv2.resize(
                    row_colors, (row_colors.shape[1], target_h),
                    interpolation=cv2.INTER_LINEAR,
                )
        # 轻微纵向平滑，避免产生明显的横向色带。
        padded = np.pad(row_colors, ((5, 5), (0, 0)), mode="edge")
        smoothed = np.vstack(
            [padded[i : i + 11].mean(axis=0) for i in range(target_h)]
        )
        fill = np.repeat(smoothed[:, None, :], right - left, axis=1)
        noise = rng.normal(0, noise_sigma, fill.shape[:2])[:, :, None]
        result[top:bottom, left:right] = np.clip(fill + noise, 0, 255).astype(np.uint8)

    return result


# ───────────────────────────── 移动：复制原生像素块 ─────────────────────────────


def move_block(
    image: np.ndarray,
    *,
    content_x: tuple[int, int],
    source_y: tuple[int, int],
    shift_y: int,
    cleanup_boxes: Iterable[Box] | None = None,
    cleanup_ink_threshold: int = 246,
) -> tuple[np.ndarray, np.ndarray]:
    """上移原扫描像素块，并清理原位置的残留墨迹。

    参数:
        content_x: 移动区域横向范围 (x1, x2)
        source_y: 移动区域纵向范围 (y1, y2)
        shift_y: 上移像素数（正值=上移）
        cleanup_boxes: 需要清理残留墨迹的区域；不给则自动用源区域尾部

    返回 (移动后图像, 清理蒙版)。
    """
    x1, x2 = content_x
    y1, y2 = source_y
    result = image.copy()
    result[y1 - shift_y : y2 - shift_y, x1:x2] = image[y1:y2, x1:x2]

    if cleanup_boxes is None:
        cleanup_boxes = [(x1, y2 - shift_y, x2, y2)]

    mask = ink_mask_in_boxes(
        image, cleanup_boxes, threshold=cleanup_ink_threshold, dilation=5
    )
    return inpaint_rgb(result, mask), mask


def move_and_clear(
    image: np.ndarray,
    *,
    content_x: tuple[int, int],
    source_y: tuple[int, int],
    shift_y: int,
    clear_boxes: Iterable[Box],
    noise_sigma: float = 0.45,
    seed: int = 20260805,
) -> np.ndarray:
    """复合操作：保存源块 -> 清除多个区域 -> 粘贴源块到新位置。

    原项目 process_chongqing_redline_cleanup.py 的工作流（复现对比 G6）：
    先复制蓝框内容，再用插值填底清除红线区域 + 蓝框原位，最后把蓝框粘贴到上移位置。
    与 ``move_block`` 的区别：清除用插值填底（整矩形），且可一次清除多个额外区域。

    参数:
        content_x: 移动区域横向范围 (x1, x2)
        source_y: 移动区域纵向范围 (y1, y2)
        shift_y: 上移像素数（正值=上移）
        clear_boxes: 需要清除的所有区域（通常包含源区域本身 + 其他需清除的区域）

    返回移动并清除后的图像。
    """
    x1, x2 = content_x
    y1, y2 = source_y
    block = image[y1:y2, x1:x2].copy()

    # 先清除所有指定区域（含源区域本身），再粘贴保存的块到新位置。
    result = remove_regions_interpolate(
        image, clear_boxes, noise_sigma=noise_sigma, seed=seed
    )

    dest_y1 = y1 - shift_y
    dest_y2 = y2 - shift_y
    result[dest_y1:dest_y2, x1:x2] = block
    return result


# ───────────────────────────── 替换：原生供体归一化 ─────────────────────────────


def normalize_donor_patch(
    donor_patch: np.ndarray,
    target_reference: np.ndarray,
    target_background: np.ndarray,
    *,
    mode: str = "contrast",
) -> tuple[np.ndarray, float]:
    """将供体词块的颜色映射到目标行。

    mode:
        ``"contrast"`` -- 对比度缩放：以供体纸白和墨迹中值为锚点，映射到目标行
                         纸白和参考字墨迹。保留原供体的毛边、断笔和色彩噪声（默认）。
        ``"offset"`` -- 纯底色偏移：donor + (target_bg - donor_bg)，不缩放对比度。
                       原项目 paste_native_number 的归一化方式，适合供体与目标
                       纸色色调一致但亮度有偏移的场景（复现对比 G3）。

    返回 (归一化后的供体, 对比度倍率；offset 模式恒为 1.0)。
    """
    if mode == "offset":
        donor_bg_pixels = donor_patch[luma(donor_patch) > 245]
        if len(donor_bg_pixels) == 0:
            donor_bg_pixels = donor_patch.reshape(-1, 3)
        target_bg_pixels = target_background[luma(target_background) > 245]
        if len(target_bg_pixels) == 0:
            target_bg_pixels = target_background.reshape(-1, 3)
        donor_bg = np.median(donor_bg_pixels, axis=0)
        target_bg = np.median(target_bg_pixels, axis=0)
        normalized = np.clip(
            donor_patch.astype(np.float32) + (target_bg - donor_bg), 0, 255
        )
        return np.uint8(normalized), 1.0

    donor_bg = background_median(donor_patch)
    donor_ink = dark_median(donor_patch)
    target_bg = background_median(target_background)
    target_ink = dark_median(target_reference)

    donor_contrast = float(luma(donor_bg) - luma(donor_ink))
    target_contrast = float(luma(target_bg) - luma(target_ink))
    contrast_scale = target_contrast / donor_contrast

    normalized = target_bg + (donor_patch.astype(np.float32) - donor_bg) * contrast_scale
    return np.uint8(np.clip(normalized, 0, 255)), contrast_scale


def paste_donor_patch(
    image: np.ndarray,
    donor_patch: np.ndarray,
    destination: tuple[int, int],
    target_reference: np.ndarray,
    target_background: np.ndarray,
    *,
    feather: int = 4,
    normalize_mode: str = "contrast",
) -> tuple[np.ndarray, float]:
    """在目标位置贴入归一化后的供体词块，边缘羽化。

    返回 (贴入后的图像, 对比度倍率)。
    """
    normalized, scale = normalize_donor_patch(
        donor_patch, target_reference, target_background, mode=normalize_mode
    )
    dest_x, dest_y = destination
    patch_height, patch_width = donor_patch.shape[:2]
    alpha = feather_mask(patch_width, patch_height, edge=feather)

    result = image.astype(np.float32)
    base = result[dest_y : dest_y + patch_height, dest_x : dest_x + patch_width]
    result[dest_y : dest_y + patch_height, dest_x : dest_x + patch_width] = (
        base * (1 - alpha) + normalized.astype(np.float32) * alpha
    )
    return np.uint8(np.clip(result, 0, 255)), scale


def replace_with_donor(
    image: np.ndarray,
    donor_image: np.ndarray,
    *,
    donor_box: Box,
    remove_boxes: Iterable[Box],
    destination: tuple[int, int],
    reference_box: Box,
    feather: int = 4,
    ink_threshold: int = 180,
    mask_mode: str = "ink",
    normalize_mode: str = "contrast",
) -> tuple[np.ndarray, np.ndarray, float]:
    """完整的原生供体替换流程：清理目标 -> 归一化供体 -> 贴入。

    mask_mode 透传给 remove_regions_telea（``"ink"`` / ``"full"``，见 G2）。
    normalize_mode 透传给 normalize_donor_patch（``"contrast"`` / ``"offset"``，见 G3）。

    返回 (替换后图像, 清理蒙版, 对比度倍率)。
    """
    erased, mask = remove_regions_telea(
        image, remove_boxes, ink_threshold=ink_threshold, mask_mode=mask_mode
    )
    dx1, dy1, dx2, dy2 = donor_box
    donor_patch = donor_image[dy1:dy2, dx1:dx2]
    rx1, ry1, rx2, ry2 = reference_box
    reference = image[ry1:ry2, rx1:rx2]
    dest_x, dest_y = destination
    patch_height, patch_width = donor_patch.shape[:2]
    target_bg_patch = erased[dest_y : dest_y + patch_height, dest_x : dest_x + patch_width]

    result, scale = paste_donor_patch(
        erased, donor_patch, destination, reference, target_bg_patch,
        feather=feather, normalize_mode=normalize_mode,
    )
    return result, mask, scale


# ───────────────────────────── 差分与验证 ─────────────────────────────


def image_diff(before: np.ndarray, after: np.ndarray) -> DiffStats:
    """计算两图的差异像素数和外框。"""
    if before.shape != after.shape:
        raise ValueError(f"图像尺寸不一致: {before.shape} != {after.shape}")
    changed = np.any(before != after, axis=2)
    ys, xs = np.where(changed)
    if not len(xs):
        return DiffStats(0, None)
    return DiffStats(
        int(changed.sum()),
        (int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)),
    )


def changes_outside_boxes(
    before: np.ndarray, after: np.ndarray, boxes: Iterable[Box]
) -> int:
    """计算允许区域外的变化像素数，应为 0。"""
    if before.shape != after.shape:
        raise ValueError(f"图像尺寸不一致: {before.shape} != {after.shape}")
    allowed = np.zeros(before.shape[:2], dtype=bool)
    for x1, y1, x2, y2 in boxes:
        allowed[y1:y2, x1:x2] = True
    changed = np.any(before != after, axis=2)
    return int(np.count_nonzero(changed & ~allowed))


def blank_region_dark_pixels(
    image: np.ndarray, box: Box, *, threshold: int = 180
) -> int:
    """检查空白区域的深色像素数，用于验证删除是否干净。"""
    x1, y1, x2, y2 = box
    return int(np.count_nonzero(luma(image[y1:y2, x1:x2]) < threshold))


def sha256_file(path: Path) -> str:
    """计算文件的 SHA-256。"""
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ───────────────────────────── 字体辅助 ─────────────────────────────


def find_cjk_font() -> Path | None:
    """为说明图标签寻找跨平台中文字体；核心页面编辑不依赖该字体。

    统一走 font_registry，与 identify_font / scan_text_fusion 共用同一注册表。
    """
    resolved = font_registry.default_cjk_font()
    return Path(resolved[0]) if resolved else None


def load_label_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """加载用于说明图标签的中文字体。"""
    path = find_cjk_font()
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default()
