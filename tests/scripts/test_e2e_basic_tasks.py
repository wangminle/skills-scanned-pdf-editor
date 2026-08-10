#!/usr/bin/env python3
"""basic-tests 五项任务的结构与合成冒烟门禁（可选本地视觉回归）。

本文件 **不是** 完整的端到端视觉回归——完整「加字且字体像素级一致」依赖
本机字体，无法在 CI 稳定运行。实际覆盖：

1. 结构门禁：各 task 源 PDF 存在、可 export-page（含 /Rotate 朝向）、
   task001 旋转往返尺寸一致
2. 合成冒烟：定位模块（行带/单字/多字供体）与删除/移动/替换像素路径在
   合成图上的确定性（不依赖本机字体）
3. 可选本地视觉回归（``TestGoldenRegression``）：仅当 ``tests/期望效果/``
   与 ``tests/results/<最新结果>/final.pdf`` 同时存在时，回渲 final.pdf 与
   期望 PNG 做 ``diff>10`` 像素百分比校验（按 task 差异化阈值）。资产缺失
   则 skip——CI 不受影响，本地跑则真实校验，避免「假绿」（BUG-068）。

字体不可用时由 ``identify_font`` 阻断（exit 3），不在本文件覆盖。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "skills" / "scanned-pdf-editor" / "scripts"
TASKS_DIR = ROOT / "tests" / "测试任务"
EXPECT_DIR = ROOT / "tests" / "期望效果"
RESULTS_DIR = ROOT / "tests" / "results"

sys.path.insert(0, str(SCRIPTS_DIR))
import locate_content  # noqa: E402
import scan_edit_ops as ops  # noqa: E402
import scan_edit_utils as utils  # noqa: E402


TASK_NAMES = [
    "task001-增加内容并保持字体效果一致",
    "task002-增加内容并保持字体效果一致",
    "task003-删除内容调整位置",
    "task004-删除内容并替换文字",
    "task005-删除内容并替换文字",
]


def _first_pdf(task_dir: Path) -> Path | None:
    pdfs = sorted(task_dir.glob("*.pdf"))
    return pdfs[0] if pdfs else None


class TestBasicTasksExportGate(unittest.TestCase):
    """五项 task 源 PDF：内嵌导出与旋转元数据门禁。"""

    def test_all_tasks_have_pdf(self):
        missing = []
        for name in TASK_NAMES:
            d = TASKS_DIR / name
            if not d.is_dir() or _first_pdf(d) is None:
                missing.append(name)
        self.assertEqual(missing, [], f"缺少源 PDF: {missing}")

    def test_export_page_each_task(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("需要 PyMuPDF")
        for name in TASK_NAMES:
            pdf = _first_pdf(TASKS_DIR / name)
            self.assertIsNotNone(pdf, name)
            with self.subTest(task=name):
                meta = utils.extract_embedded_page_image(pdf, page_index=0, as_displayed=True)
                self.assertGreater(meta.image.width, 100)
                self.assertGreater(meta.image.height, 100)
                # 显示朝向尺寸应与 embedded 经 rotate 后一致
                self.assertEqual(meta.image.size, meta.displayed_size)

    def test_task001_rotate_270_export_roundtrip(self):
        """task001 典型 /Rotate 270：显示朝向编辑后 package 可旋回。"""
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("需要 PyMuPDF")
        pdf = _first_pdf(TASKS_DIR / TASK_NAMES[0])
        if pdf is None:
            self.skipTest("无 task001 PDF")
        meta = utils.extract_embedded_page_image(pdf, page_index=0, as_displayed=False)
        if meta.rotate == 0:
            self.skipTest("该 PDF 无 /Rotate，跳过旋转往返")
        displayed = utils.orient_embedded_to_displayed(meta.image, meta.rotate)
        # 模拟局部编辑（右下角涂一点）
        arr = np.asarray(displayed).copy()
        arr[-20:, -20:] = (10, 10, 10)
        edited = Image.fromarray(arr)
        prepared = utils.prepare_image_for_pdf_replace(
            edited,
            embedded_size=meta.embedded_size,
            displayed_size=meta.displayed_size,
            rotate=meta.rotate,
        )
        self.assertEqual(prepared.size, meta.embedded_size)


class TestLocateOnRealOrSynthetic(unittest.TestCase):
    def test_line_bands_on_synthetic_paragraph(self):
        # 三行黑字带
        img = np.full((200, 400, 3), 230, dtype=np.uint8)
        for y0 in (40, 90, 140):
            img[y0:y0 + 18, 30:370] = 40
        bands = locate_content.detect_line_bands(img, (20, 20, 390, 190), min_height=10)
        self.assertGreaterEqual(len(bands), 3)

    def test_donor_search_finds_similar_glyph(self):
        img = np.full((120, 300, 3), 240, dtype=np.uint8)
        # 参考字
        img[30:60, 40:70] = 20
        # 供体字（同高）
        img[30:60, 200:230] = 20
        hits = locate_content.find_donor_candidates(
            img,
            (40, 30, 70, 60),
            (0, 0, 300, 120),
        )
        self.assertGreaterEqual(len(hits), 1)
        box = hits[0][0].as_box()
        # 连通域/膨胀可能扩 1px，允许近似
        self.assertAlmostEqual(box[0], 200, delta=2)
        self.assertAlmostEqual(box[1], 30, delta=2)
        self.assertAlmostEqual(box[2], 230, delta=2)
        self.assertAlmostEqual(box[3], 60, delta=2)

    def test_donor_search_multi_char_word_block(self):
        """BUG-067：多字符参考框（如「结案」）应由多连通域组合命中。

        参考框宽 ~60（两字），搜索区另有一组同尺寸双块；旧实现只比单连通域，
        ref_w=60 远超单字 30 → 返回 0。修复后聚行合并应返回 ≥1 组合候选。
        """
        img = np.full((120, 400, 3), 240, dtype=np.uint8)
        # 参考块：两个分离字符（模拟「结案」），框宽 ~95（30+5 间隔+30+边距）
        img[30:60, 40:70] = 20     # 字1
        img[30:60, 80:110] = 20    # 字2（与字1同行，5px 间距由白边形成）
        # 供体块：另一组同尺寸双字
        img[30:60, 250:280] = 20
        img[30:60, 290:320] = 20
        hits = locate_content.find_donor_candidates(
            img,
            reference_box=(38, 28, 112, 62),   # 包住参考双字，宽 74 高 34
            search_region=(0, 0, 400, 120),
        )
        self.assertGreaterEqual(len(hits), 1, "多字符参考框应能命中组合供体")
        # 最佳候选应落在供体块区域（x≈248-322）
        box = hits[0][0].as_box()
        self.assertGreater(box[0], 200, f"候选 x1 应在供体区，得到 {box}")
        self.assertLess(box[0], 260, f"候选 x1 应靠近供体起点，得到 {box}")
        self.assertGreater(box[2], 280, f"候选 x2 应覆盖第二字，得到 {box}")

    def test_donor_search_single_char_still_works(self):
        """BUG-067 回归：单字符参考框仍命中单连通域，多字路径不影响。"""
        img = np.full((120, 300, 3), 240, dtype=np.uint8)
        img[30:60, 40:70] = 20
        img[30:60, 200:230] = 20
        hits = locate_content.find_donor_candidates(
            img, (40, 30, 70, 60), (0, 0, 300, 120),
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0][0].x1, 200, delta=2)

    def test_donor_search_does_not_cluster_across_rows(self):
        """BUG-067：不同行的连通域不应被误聚为同一组合候选。"""
        img = np.full((200, 300, 3), 240, dtype=np.uint8)
        # 第1行单字（参考框同行位置）
        img[30:60, 40:70] = 20
        # 第2行单字（y 差远超 ref_h，不应与第1行聚）
        img[130:160, 200:230] = 20
        # 参考框：宽跨两字（不可能在一行内找到合法组合）
        hits = locate_content.find_donor_candidates(
            img,
            reference_box=(40, 30, 100, 60),  # 宽 60，但同行只有单字 30
            search_region=(0, 0, 300, 200),
        )
        # 不应把第1行字 + 第2行字误合为 60 宽候选
        for box, _score in hits:
            self.assertLess(box.y2 - box.y1, 50, "跨行连通域不应被聚成一个候选")

    def test_locate_cli_lines(self):
        tmp = Path(tempfile.mkdtemp()) / "p.png"
        img = np.full((100, 200, 3), 230, dtype=np.uint8)
        img[40:55, 20:180] = 30
        Image.fromarray(img).save(tmp)
        rc = locate_content.main(["lines", "--source", str(tmp), "--region", "0,0,200,100"])
        self.assertEqual(rc, 0)


class TestOpsVisualSmoke(unittest.TestCase):
    """删除/移动/供体路径确定性冒烟（对应 task003–005 能力基线）。"""

    def test_remove_then_move_preserves_outside(self):
        src = np.full((200, 200, 3), 220, dtype=np.uint8)
        src[50:70, 40:160] = 30  # 行1 待删
        src[90:110, 40:160] = 30  # 行2 待上移
        out, _mask = utils.remove_regions_telea(src, [(40, 50, 160, 70)])
        moved = utils.move_and_clear(
            out,
            content_x=(40, 160),
            source_y=(90, 110),
            shift_y=40,
            clear_boxes=[(40, 90, 160, 110)],
        )
        # 远区不变
        self.assertTrue(np.array_equal(src[0:20, 0:20], moved[0:20, 0:20]))
        # 行2 原位应被清除（变浅）；行1 位被上移内容占据（仍偏暗）
        self.assertGreater(moved[90:110, 40:160].mean(), 100)
        self.assertLess(moved[50:70, 40:160].mean(), 80)

    def test_replace_with_donor_smoke(self):
        base = np.full((100, 200, 3), 230, dtype=np.uint8)
        # 目标字与供体字：框内留纸白边，满足 contrast 归一化
        base[25:45, 25:45] = 40
        base[25:45, 125:145] = 40
        out, _mask, _offset = utils.replace_with_donor(
            base,
            base,
            donor_box=(120, 20, 150, 50),
            remove_boxes=[(20, 20, 50, 50)],
            destination=(20, 20),
            reference_box=(120, 20, 150, 50),
            feather=2,
            normalize_mode="offset",
        )
        self.assertEqual(out.shape, base.shape)


class TestExpectedAssetsPresent(unittest.TestCase):
    """期望效果资产存在性检查（结构门禁，非视觉对比）。"""

    def test_expected_assets_exist_for_tasks(self):
        # 不强制每个 task 都有期望图，但目录应存在且至少 task001 有对照
        self.assertTrue(EXPECT_DIR.is_dir(), "缺少 tests/期望效果")
        t1 = EXPECT_DIR / TASK_NAMES[0]
        pngs = list(t1.glob("*.png")) if t1.is_dir() else []
        self.assertGreater(len(pngs), 0, "task001 期望效果应至少有一张 PNG")


class TestGoldenRegression(unittest.TestCase):
    """可选本地视觉回归：回渲结果 final.pdf 与期望 PNG 做 diff>10 百分比校验。

    仅当 tests/期望效果/<task>/ 与 tests/results/<最新结果>/final.pdf 同时
    存在时运行；资产缺失（CI / 干净克隆）则 skip。避免 BUG-068 的假绿：
    旧测试只用零数组自比，视觉回归发生时仍通过。
    """

    # 按 task 差异化阈值（diff>10 像素占全页百分比上限）。
    # ⚠️ 注意：tests/期望效果/ 的 golden PNG 是早期手动项目用未知光栅化器生成的，
    # 与本测试的 PyMuPDF 渲染存在全页级光栅化底噪（task003≈11%、task004/005≈4.5%），
    # 远大于真实编辑差异（过程记录曾报 0.04~0.07%）。故这些阈值反映「光栅化底噪
    # +余量」而非编辑精度，仅用于捕捉灾难性回归。golden 重新用本仓库渲染器生成后
    # 应收紧到 <1%。详见 CHK 复盘记录。
    THRESHOLDS = {
        TASK_NAMES[2]: 0.15,   # task003：实测 ~11%，留余量到 15%
        TASK_NAMES[3]: 0.07,   # task004：实测 ~4.4%，留余量到 7%
        TASK_NAMES[4]: 0.07,   # task005：实测 ~4.5%，留余量到 7%
    }

    def _latest_result_for(self, task_name: str) -> Path | None:
        """找 results 下最新的对应 task 结果目录中的 final.pdf。"""
        if not RESULTS_DIR.is_dir():
            return None
        candidates = sorted(
            d for d in RESULTS_DIR.iterdir()
            if d.is_dir() and task_name.split("-")[0] in d.name
        )
        for d in reversed(candidates):
            final = d / "final.pdf"
            if final.exists():
                return final
        return None

    def _golden_png(self, task_name: str) -> Path | None:
        d = EXPECT_DIR / task_name
        if not d.is_dir():
            return None
        pngs = sorted(d.glob("*.png"))
        # 取全页图（最大尺寸），排除 _crop 缩略
        full = [p for p in pngs if "crop" not in p.name.lower()]
        return (full or pngs)[0] if (full or pngs) else None

    def _render_pdf_to_array(self, pdf: Path, target_size: tuple[int, int]) -> np.ndarray:
        """按 golden 尺寸反推 dpi 渲染，避免 resize 引入重采样差异。"""
        import fitz
        doc = fitz.open(str(pdf))
        try:
            page = doc[0]
            tw, th = target_size
            # 反推 dpi：golden 像素 / 页面点尺寸 × 72
            zoom_x = tw / page.rect.width
            zoom_y = th / page.rect.height
            mat = fitz.Matrix(zoom_x, zoom_y)
            pix = page.get_pixmap(matrix=mat)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            return arr[..., :3]
        finally:
            doc.close()

    def _diff_gt_threshold_ratio(self, a: np.ndarray, b: np.ndarray) -> float:
        """两图同尺寸后，|delta|>10 像素占全页比例。

        golden 与渲染结果常有 ±1px 尺寸差（不同光栅化器），先 resize 对齐再比。
        """
        if a.shape != b.shape:
            b = np.asarray(
                Image.fromarray(b).resize((a.shape[1], a.shape[0]), Image.BILINEAR)
            )
        delta = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
        return float((delta > 10).mean())

    def test_golden_regression_per_task(self):
        if not EXPECT_DIR.is_dir():
            self.skipTest("无 tests/期望效果（CI / 干净克隆）")
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("需要 PyMuPDF")

        ran_any = False
        for task_name, threshold in self.THRESHOLDS.items():
            golden = self._golden_png(task_name)
            final_pdf = self._latest_result_for(task_name)
            if golden is None or final_pdf is None:
                continue
            with self.subTest(task=task_name):
                golden_img = Image.open(golden).convert("RGB")
                golden_arr = np.asarray(golden_img)
                rendered = self._render_pdf_to_array(final_pdf, golden_img.size)
                ratio = self._diff_gt_threshold_ratio(rendered, golden_arr)
                self.assertLess(
                    ratio, threshold,
                    f"{task_name}: diff>10 = {ratio:.4f} 超过阈值 {threshold} "
                    f"(golden={golden.name}, result={final_pdf.parent.name})",
                )
            ran_any = True
        if not ran_any:
            self.skipTest("无可用 golden+result 对（task001/002 字体依赖或结果未生成）")


class TestExportPageCliOnTaskPdf(unittest.TestCase):
    def test_cli_export_task003(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("需要 PyMuPDF")
        pdf = _first_pdf(TASKS_DIR / TASK_NAMES[2])
        if pdf is None:
            self.skipTest("无 task003")
        out = Path(tempfile.mkdtemp()) / "p.png"
        rc = ops.main([
            "export-page", "--pdf", str(pdf), "--output", str(out), "--as-displayed",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        img = Image.open(out)
        self.assertGreater(img.width * img.height, 10_000)


if __name__ == "__main__":
    unittest.main()
