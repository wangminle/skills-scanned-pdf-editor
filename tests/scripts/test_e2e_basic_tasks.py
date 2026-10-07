#!/usr/bin/env python3
"""basic-tests 五项任务的结构与合成冒烟门禁（可选本地视觉回归）。

本文件 **不是** 完整的端到端视觉回归——完整「加字且字体像素级一致」依赖
本机字体，无法在 CI 稳定运行。实际覆盖：

1. 结构门禁：各 task 源 PDF 存在、可 export-page（含 /Rotate 朝向）、
   task001 旋转往返尺寸一致
2. 合成冒烟：定位模块（行带/单字/多字供体）与删除/移动/替换像素路径在
   合成图上的确定性（不依赖本机字体）
3. 可选本地视觉回归（``TestGoldenRegression``）：仅当 ``tests/期望效果/``
   与 ``tests/results/<同批次结果>/taskNNN_result.pdf``（或旧名 final.pdf）同时存在时，回渲交付 PDF 与
   期望 PNG 做 ``diff>10`` 像素百分比校验（按 task 差异化阈值）。资产缺失
   则 skip——CI 不受影响，本地跑则真实校验，避免「假绿」（BUG-068）。

字体不可用时由 ``identify_font`` 阻断（exit 3），不在本文件覆盖。
"""
from __future__ import annotations

import sys
import os
import re
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
        # BUG-074：夹具目录 tests/测试任务/ 按设计被 .gitignore 排除（大体积二进制，
        # 不随仓库分发）。干净克隆 / CI 上目录缺失，本用例与 golden 用例统一按
        # 「可选」处理；目录存在时仍严格校验，作为内部完整检出的资产完整性检查。
        if not TASKS_DIR.is_dir():
            self.skipTest("无 tests/测试任务（干净克隆 / CI）")
        missing = []
        for name in TASK_NAMES:
            d = TASKS_DIR / name
            if not d.is_dir() or _first_pdf(d) is None:
                missing.append(name)
        self.assertEqual(missing, [], f"缺少源 PDF: {missing}")

    def test_export_page_each_task(self):
        # BUG-074：同 test_all_tasks_have_pdf，夹具缺失（干净克隆 / CI）时跳过。
        if not TASKS_DIR.is_dir():
            self.skipTest("无 tests/测试任务（干净克隆 / CI）")
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
        # BUG-074：tests/期望效果/ 同样被 .gitignore 排除（大体积二进制）。干净克隆 /
        # CI 上目录缺失时与 golden 用例一致 skip，不再硬断言制造必然三红；目录存在
        # 时仍校验，作为内部完整检出的资产完整性检查。
        if not EXPECT_DIR.is_dir():
            self.skipTest("无 tests/期望效果（干净克隆 / CI）")
        # 不强制每个 task 都有期望图，但至少 task001 有对照
        t1 = EXPECT_DIR / TASK_NAMES[0]
        pngs = list(t1.glob("*.png")) if t1.is_dir() else []
        self.assertGreater(len(pngs), 0, "task001 期望效果应至少有一张 PNG")


class TestGoldenRegression(unittest.TestCase):
    """可选本地视觉回归：同批次交付 PDF 与期望 PNG 做 diff>10 百分比校验。

    默认选择最新日期批次，可用 SCANNED_PDF_RESULTS_BATCH=YYYYMMDD 明确绑定。
    无资产的普通 CI 可跳过；显式绑定或已有批次缺少交付/期望文件必须失败。
    """

    # 按 task 差异化阈值（diff>10 像素占全页百分比上限）。
    # ⚠️ 注意：tests/期望效果/ 的 golden PNG 是早期手动项目用未知光栅化器生成的，
    # 跨光栅化器比对并不证明像素一致。固定300dpi、golden双线性缩放的20261007
    # 批次实测为7.67%/1.05%/1.01%。task003未编辑源为10.62%，阈值9%拒绝原样交付；
    # 字体/局部保留等质量仍需专项审计。golden同源重建后再校准阈值。见CHK-049。
    THRESHOLDS = {
        TASK_NAMES[2]: 0.09,
        TASK_NAMES[3]: 0.07,
        TASK_NAMES[4]: 0.07,
    }

    def _latest_result_for(self, task_name: str) -> Path | None:
        """在同一批次选择最新任务目录；缺文件直接失败，绝不回退旧结果。"""
        requested = os.environ.get("SCANNED_PDF_RESULTS_BATCH")
        if requested is not None:
            self.assertRegex(requested, r"^\d{8}$", "结果批次须为 YYYYMMDD")
        directories = sorted(
            d for d in RESULTS_DIR.iterdir()
            if d.is_dir() and re.match(r"^\d{8}-", d.name)
            and any(name.split("-")[0] in d.name for name in TASK_NAMES)
        ) if RESULTS_DIR.is_dir() else []
        if not directories and requested is None:
            return None
        batch = requested or directories[-1].name[:8]
        code = task_name.split("-")[0]
        candidates = [d for d in directories
                      if d.name.startswith(batch + "-") and code in d.name]
        self.assertTrue(candidates, f"批次 {batch} 缺少 {code} 结果目录")
        latest = candidates[-1]
        outputs = [latest / name for name in (f"{code}_result.pdf", "final.pdf")
                   if (latest / name).is_file()]
        self.assertEqual(len(outputs), 1,
                         f"{latest}: 必须有唯一交付 PDF（{code}_result.pdf 或 final.pdf）")
        return outputs[0]

    def _golden_png(self, task_name: str) -> Path | None:
        d = EXPECT_DIR / task_name
        if not d.is_dir():
            return None
        pngs = sorted(d.glob("*.png"))
        # 取全页图（最大尺寸），排除 _crop 缩略
        full = [p for p in pngs if "crop" not in p.name.lower()]
        return (full or pngs)[0] if (full or pngs) else None

    def _render_pdf_to_array(self, pdf: Path) -> np.ndarray:
        """固定300dpi回渲，与报告同口径；比对时将golden双线性缩放到此尺寸。"""
        import fitz
        doc = fitz.open(str(pdf))
        try:
            page = doc[0]
            pix = page.get_pixmap(dpi=300, colorspace=fitz.csRGB, alpha=False)
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
            if os.environ.get("SCANNED_PDF_RESULTS_BATCH") is not None:
                self.fail("显式绑定批次需要 tests/期望效果 资产")
            self.skipTest("无 tests/期望效果（CI / 干净克隆）")
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("需要 PyMuPDF")

        ran_any = False
        for task_name, threshold in self.THRESHOLDS.items():
            golden = self._golden_png(task_name)
            final_pdf = self._latest_result_for(task_name)
            if final_pdf is None:
                continue
            self.assertIsNotNone(golden, f"本批 {task_name} 缺少期望 PNG")
            with self.subTest(task=task_name):
                golden_img = Image.open(golden).convert("RGB")
                golden_arr = np.asarray(golden_img)
                rendered = self._render_pdf_to_array(final_pdf)
                ratio = self._diff_gt_threshold_ratio(rendered, golden_arr)
                print(f"golden_checked={final_pdf} diff_gt10={ratio:.6%}")
                self.assertLess(
                    ratio, threshold,
                    f"{task_name}: diff>10 = {ratio:.4f} 超过阈值 {threshold} "
                    f"(golden={golden.name}, result={final_pdf.parent.name})",
                )
            ran_any = True
        if not ran_any:
            self.skipTest("无可用 golden+result 对（task001/002 字体依赖或结果未生成）")


class TestBug080GoldenResultSelection(unittest.TestCase):
    """真实目录验证：固定同一批次，缺失结果不得回退历史交付。"""

    def setUp(self):
        from unittest.mock import patch
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.results = Path(self.tmp.name)
        patcher = patch(__name__ + ".RESULTS_DIR", self.results)
        patcher.start()
        self.addCleanup(patcher.stop)
        env = patch.dict("os.environ", {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        import os
        os.environ.pop("SCANNED_PDF_RESULTS_BATCH", None)
        self.selector = TestGoldenRegression()

    def result(self, date, code, filename):
        directory = self.results / f"{date}-0001-{code}"
        directory.mkdir(exist_ok=True)
        if filename:
            (directory / filename).touch()
        return directory

    def test_current_filename_beats_historical_final(self):
        self.result("20260809", "task003", "final.pdf")
        latest = self.result("20261007", "task003", "task003_result.pdf")
        self.assertEqual(self.selector._latest_result_for(TASK_NAMES[2]),
                         latest / "task003_result.pdf")

    def test_missing_latest_file_fails_instead_of_falling_back(self):
        self.result("20260809", "task003", "final.pdf")
        self.result("20261007", "task003", None)
        with self.assertRaises(AssertionError):
            self.selector._latest_result_for(TASK_NAMES[2])

    def test_missing_task_in_latest_batch_fails(self):
        self.result("20260809", "task003", "final.pdf")
        self.result("20261007", "task004", "task004_result.pdf")
        with self.assertRaises(AssertionError):
            self.selector._latest_result_for(TASK_NAMES[2])

    def test_explicit_batch_stays_bound(self):
        from unittest.mock import patch
        older = self.result("20260809", "task003", "final.pdf")
        self.result("20261007", "task003", "task003_result.pdf")
        with patch.dict("os.environ", {"SCANNED_PDF_RESULTS_BATCH": "20260809"}):
            self.assertEqual(self.selector._latest_result_for(TASK_NAMES[2]),
                             older / "final.pdf")

    def test_two_final_names_are_ambiguous(self):
        latest = self.result("20261007", "task003", "final.pdf")
        (latest / "task003_result.pdf").touch()
        with self.assertRaises(AssertionError):
            self.selector._latest_result_for(TASK_NAMES[2])

    def test_legacy_final_supported(self):
        latest = self.result("20260809", "task003", "final.pdf")
        self.assertEqual(self.selector._latest_result_for(TASK_NAMES[2]),
                         latest / "final.pdf")

    def test_explicit_batch_requires_golden_assets(self):
        from unittest.mock import patch
        with patch(__name__ + ".EXPECT_DIR", self.results / "missing-golden"), \
                patch.dict("os.environ", {"SCANNED_PDF_RESULTS_BATCH": "20261007"}):
            try:
                self.selector.test_golden_regression_per_task()
            except unittest.SkipTest:
                self.fail("显式批次缺少golden不能静默跳过")
            except AssertionError:
                return
            self.fail("显式批次缺少golden应失败")

    def test_report_and_gate_use_300dpi_render_basis(self):
        import fitz
        pdf = self.results / "page.pdf"
        with fitz.open() as doc:
            doc.new_page(width=72, height=72)
            doc.save(pdf)
        # 一英寸页必须渲染为300px，不能按任意golden尺寸反推分辨率。
        rendered = self.selector._render_pdf_to_array(pdf)
        self.assertEqual(rendered.shape[:2], (300, 300))


class TestBug082GoldenNoOp(unittest.TestCase):
    def test_task003_rejects_unedited_source_as_delivery(self):
        """把真实未编辑源PDF冒充本批交付，必须被golden门禁拒绝。"""
        import shutil
        from unittest.mock import patch
        source = _first_pdf(TASKS_DIR / TASK_NAMES[2])
        if source is None or TestGoldenRegression()._golden_png(TASK_NAMES[2]) is None:
            self.skipTest("需要task003源PDF与golden资产")
        with tempfile.TemporaryDirectory() as folder:
            results = Path(folder)
            delivery = results / "20261007-0001-task003" / "task003_result.pdf"
            delivery.parent.mkdir()
            shutil.copy2(source, delivery)
            thresholds = {TASK_NAMES[2]: TestGoldenRegression.THRESHOLDS[TASK_NAMES[2]]}
            with patch(__name__ + ".RESULTS_DIR", results), \
                    patch.object(TestGoldenRegression, "THRESHOLDS", thresholds), \
                    patch.dict("os.environ", {"SCANNED_PDF_RESULTS_BATCH": "20261007"}):
                result = unittest.TestResult()
                TestGoldenRegression("test_golden_regression_per_task").run(result)
            self.assertEqual(result.errors, [], "负例不能因执行异常失败")
            self.assertEqual(len(result.failures), 1, "未编辑源PDF应被golden差异阈值拒绝")
            self.assertIn("超过阈值", result.failures[0][1])


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
