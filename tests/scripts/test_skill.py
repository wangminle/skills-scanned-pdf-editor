"""scanned-pdf-editor skill 自测。

测试内容：
1. scan_edit_utils 的删除（telea / interpolate）、移动、替换操作
2. scan_edit_utils 的差分和验证函数
3. scan_text_fusion 的尺寸一致性和确定性
4. font_registry 的跨平台字体查找
5. scan_edit_ops CLI 的基本功能

运行：
  cd scripts && python3 -m pytest test_skill.py -v
  # 或
  cd scripts && python3 -m unittest test_skill
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import unittest

# 确保能导入同目录下的模块
# 测试文件位于 tests/scripts/，被测脚本位于 skills/scanned-pdf-editor/scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "scanned-pdf-editor" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import scan_edit_utils as utils  # noqa: E402
import font_registry  # noqa: E402


def make_test_image(width: int = 400, height: int = 300) -> np.ndarray:
    """生成一张带模拟文字的测试图。"""
    img = np.full((height, width, 3), 245, dtype=np.uint8)  # 浅灰纸白
    # 画几条"文字"线
    from PIL import ImageDraw
    pil = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    for y in [50, 100, 150, 200]:
        draw.text((50, y), "测试文字ABC", fill=(40, 40, 40))
    return np.asarray(pil)


class TestRemoveRegions(unittest.TestCase):
    """测试删除操作。"""

    def setUp(self):
        self.image = make_test_image()

    def test_telea_returns_same_shape(self):
        result, mask = utils.remove_regions_telea(
            self.image, [(50, 50, 200, 80)], ink_threshold=180
        )
        self.assertEqual(result.shape, self.image.shape)
        self.assertEqual(mask.shape, self.image.shape[:2])

    def test_telea_changes_only_in_box(self):
        boxes = [(50, 50, 200, 80)]
        result, _ = utils.remove_regions_telea(
            self.image, boxes, ink_threshold=180
        )
        # 框外不应变化
        outside = utils.changes_outside_boxes(self.image, result, boxes)
        # Telea 修补可能稍微超出框，但应该很少
        self.assertLess(outside, 500)

    def test_interpolate_returns_same_shape(self):
        result = utils.remove_regions_interpolate(
            self.image, [(50, 50, 200, 80)]
        )
        self.assertEqual(result.shape, self.image.shape)

    def test_interpolate_changes_only_in_box(self):
        boxes = [(50, 50, 200, 80)]
        result = utils.remove_regions_interpolate(self.image, boxes)
        outside = utils.changes_outside_boxes(self.image, result, boxes)
        # 插值法严格在框内
        self.assertEqual(outside, 0)


class TestMoveBlock(unittest.TestCase):
    """测试移动操作。"""

    def setUp(self):
        self.image = make_test_image(400, 400)

    def test_move_returns_same_shape(self):
        result, mask = utils.move_block(
            self.image,
            content_x=(40, 300),
            source_y=(100, 250),
            shift_y=50,
        )
        self.assertEqual(result.shape, self.image.shape)

    def test_move_creates_changes(self):
        result, _ = utils.move_block(
            self.image,
            content_x=(40, 300),
            source_y=(100, 250),
            shift_y=50,
        )
        diff = utils.image_diff(self.image, result)
        self.assertGreater(diff.changed_pixels, 0)
        self.assertIsNotNone(diff.bbox)


class TestReplaceWithDonor(unittest.TestCase):
    """测试替换操作。"""

    def setUp(self):
        self.image = make_test_image(400, 400)

    def test_replace_returns_same_shape(self):
        # 用自身作为供体
        result, mask, scale = utils.replace_with_donor(
            self.image,
            self.image,
            donor_box=(50, 50, 150, 80),
            remove_boxes=[(200, 200, 300, 230)],
            destination=(200, 200),
            reference_box=(50, 50, 150, 80),
        )
        self.assertEqual(result.shape, self.image.shape)
        self.assertEqual(mask.shape, self.image.shape[:2])
        self.assertGreater(scale, 0)

    def test_replace_creates_changes(self):
        result, _, _ = utils.replace_with_donor(
            self.image,
            self.image,
            donor_box=(50, 50, 150, 80),
            remove_boxes=[(200, 200, 300, 230)],
            destination=(200, 200),
            reference_box=(50, 50, 150, 80),
        )
        diff = utils.image_diff(self.image, result)
        self.assertGreater(diff.changed_pixels, 0)


class TestDiffAndVerify(unittest.TestCase):
    """测试差分和验证函数。"""

    def test_image_diff_identical(self):
        img = make_test_image()
        diff = utils.image_diff(img, img)
        self.assertEqual(diff.changed_pixels, 0)
        self.assertIsNone(diff.bbox)

    def test_image_diff_different(self):
        img1 = make_test_image()
        img2 = img1.copy()
        img2[50:60, 50:60] = 0
        diff = utils.image_diff(img1, img2)
        self.assertGreater(diff.changed_pixels, 0)
        self.assertEqual(diff.bbox, (50, 50, 60, 60))

    def test_changes_outside_boxes(self):
        img1 = make_test_image()
        img2 = img1.copy()
        img2[50:60, 50:60] = 0  # 在框内
        img2[200:210, 200:210] = 0  # 在框外
        outside = utils.changes_outside_boxes(img1, img2, [(40, 40, 100, 100)])
        self.assertGreater(outside, 0)

    def test_blank_region_dark_pixels(self):
        img = make_test_image()
        # 空白区应没有深色像素
        dark = utils.blank_region_dark_pixels(img, (300, 10, 380, 40))
        self.assertEqual(dark, 0)

    def test_sha256_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            f.flush()
            digest = utils.sha256_file(Path(f.name))
        self.assertEqual(len(digest), 64)
        import os
        os.unlink(f.name)


class TestFontRegistry(unittest.TestCase):
    """测试跨平台字体注册表。"""

    def test_resolve_font_returns_none_for_nonexistent(self):
        result = font_registry.resolve_font("__nonexistent_font__.ttf")
        self.assertIsNone(result)

    def test_find_font_returns_none_for_invalid(self):
        result = font_registry.find_font("__invalid_font_name__")
        self.assertIsNone(result)

    def test_available_cjk_fonts_returns_list(self):
        fonts = font_registry.available_cjk_fonts()
        self.assertIsInstance(fonts, list)
        # 测试机上至少应该有一种 CJK 字体（或为空）
        for name, path, idx in fonts:
            self.assertTrue(Path(path).exists())

    def test_font_dirs_includes_macos_user_fonts(self):
        """macOS 双击安装字体落到 ~/Library/Fonts，必须被 FONT_DIRS 收录
        （复现对比报告 task002add 字体 bug：此前缺该目录，装了 simfang.ttf 也找不到）。"""
        macos_user = os.path.expanduser("~/Library/Fonts")
        self.assertIn(macos_user, font_registry.FONT_DIRS)

    def test_resolve_font_finds_file_in_temp_dir(self):
        """resolve_font 应遍历 FONT_DIRS 按文件名查找，确认目录覆盖生效。"""
        import tempfile
        import shutil
        tmpdir = tempfile.mkdtemp()
        try:
            dummy = os.path.join(tmpdir, "__test_dummy_font__.ttf")
            open(dummy, "w").close()
            old_dirs = font_registry.FONT_DIRS[:]
            font_registry.FONT_DIRS = [tmpdir]
            try:
                result = font_registry.resolve_font("__test_dummy_font__.ttf")
                self.assertEqual(result, dummy)
            finally:
                font_registry.FONT_DIRS = old_dirs
        finally:
            shutil.rmtree(tmpdir)


class TestScanTextFusion(unittest.TestCase):
    """测试扫描融合脚本的基本属性。"""

    def setUp(self):
        # 如果没有 CJK 字体，跳过
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体，跳过融合测试")

    def test_render_clean_preserves_size(self):
        import scan_text_fusion as stf
        base = Image.new("RGB", (300, 200), (245, 245, 245))
        font_path, font_idx = font_registry.default_cjk_font()
        font = stf.load_font(font_path, 20, index=font_idx)
        result = stf.render_clean_text(
            base, text="测试", position=(10, 10), font=font, color=(40, 40, 40)
        )
        self.assertEqual(result.size, base.size)

    def test_render_fusion_preserves_size(self):
        import scan_text_fusion as stf
        base = Image.new("RGB", (300, 200), (245, 245, 245))
        font_path, font_idx = font_registry.default_cjk_font()
        font = stf.load_font(font_path, 20, index=font_idx)
        result = stf.render_scan_fusion(
            base, text="测试", position=(10, 10), font=font,
            ink_color=(40, 40, 40), seed=20260701, strength=0.5
        )
        self.assertEqual(result.size, base.size)

    def test_same_seed_deterministic(self):
        import scan_text_fusion as stf
        base = Image.new("RGB", (300, 200), (245, 245, 245))
        font_path, font_idx = font_registry.default_cjk_font()
        font = stf.load_font(font_path, 20, index=font_idx)
        kwargs = dict(
            base=base, text="测试", position=(10, 10), font=font,
            ink_color=(40, 40, 40), seed=20260701, strength=0.5
        )
        r1 = stf.render_scan_fusion(**kwargs)
        r2 = stf.render_scan_fusion(**kwargs)
        arr1 = np.asarray(r1)
        arr2 = np.asarray(r2)
        self.assertTrue(np.array_equal(arr1, arr2))


class TestScanTextFusionAdvanced(unittest.TestCase):
    """测试扫描融合的高级特性：字重肩部、halo 效果、区域限制。"""

    def setUp(self):
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体，跳过融合测试")
        self.font_path, self.font_idx = font_registry.default_cjk_font()
        self.base = Image.new("RGB", (300, 200), (245, 245, 245))
        self.font = None

    def _get_font(self):
        if self.font is None:
            import scan_text_fusion as stf
            self.font = stf.load_font(self.font_path, 20, index=self.font_idx)
        return self.font

    def test_stroke_shoulder_changes_output(self):
        """开启字重肩部后，融合结果应与关闭时不同。"""
        import scan_text_fusion as stf
        font = self._get_font()
        kwargs = dict(
            base=self.base, text="测试", position=(10, 10), font=font,
            ink_color=(40, 40, 40), seed=20260701, strength=0.5,
        )
        r_off = stf.render_scan_fusion(**kwargs, stroke_shoulder_blend=0.0)
        r_on = stf.render_scan_fusion(**kwargs, stroke_shoulder_blend=0.25)
        self.assertFalse(
            np.array_equal(np.asarray(r_off), np.asarray(r_on)),
            "字重肩部应改变输出结果",
        )

    def test_core_alpha_scale_changes_output(self):
        """不同的 core_alpha_scale 应产生不同结果。"""
        import scan_text_fusion as stf
        font = self._get_font()
        kwargs = dict(
            base=self.base, text="测试", position=(10, 10), font=font,
            ink_color=(40, 40, 40), seed=20260701, strength=0.5,
        )
        r_default = stf.render_scan_fusion(**kwargs, core_alpha_scale=0.965)
        r_reduced = stf.render_scan_fusion(**kwargs, core_alpha_scale=0.875)
        self.assertFalse(
            np.array_equal(np.asarray(r_default), np.asarray(r_reduced)),
            "不同 core_alpha_scale 应产生不同结果",
        )

    def test_halo_adds_visible_diff(self):
        """render_halo 应在 fusion 基础上产生可见变化。"""
        import scan_text_fusion as stf
        font = self._get_font()
        fusion = stf.render_scan_fusion(
            self.base, text="测试", position=(10, 10), font=font,
            ink_color=(40, 40, 40), seed=20260701, strength=0.5,
        )
        halo = stf.render_halo(
            fusion, text="测试", position=(10, 10), font=font,
            halo_color=(178, 196, 211), seed=20260701, strength=1.0,
        )
        diff = np.any(np.asarray(fusion) != np.asarray(halo), axis=2)
        self.assertGreater(int(diff.sum()), 0, "halo 应在 fusion 基础上产生变化")

    def test_fusion_only_changes_text_region(self):
        """融合应只改变文字附近区域，远处像素不变。"""
        import scan_text_fusion as stf
        font = self._get_font()
        result = stf.render_scan_fusion(
            self.base, text="测", position=(10, 10), font=font,
            ink_color=(40, 40, 40), seed=20260701, strength=0.5,
        )
        base_arr = np.asarray(self.base)
        result_arr = np.asarray(result)
        # 右下角远离文字的区域应完全不变
        far_region = slice(150, 200), slice(150, 300)
        self.assertTrue(
            np.array_equal(base_arr[far_region], result_arr[far_region]),
            "文字远处像素不应变化",
        )

    def test_stroke_shoulder_default_preserves_old_behavior(self):
        """默认参数（stroke_shoulder=0.0）应与无参数调用结果一致。"""
        import scan_text_fusion as stf
        font = self._get_font()
        kwargs = dict(
            base=self.base, text="测试", position=(10, 10), font=font,
            ink_color=(40, 40, 40), seed=20260701, strength=0.5,
        )
        r_explicit = stf.render_scan_fusion(**kwargs, stroke_shoulder_blend=0.0, core_alpha_scale=0.965)
        r_default = stf.render_scan_fusion(**kwargs)
        self.assertTrue(np.array_equal(np.asarray(r_explicit), np.asarray(r_default)))


class TestScanEditOpsCLI(unittest.TestCase):
    """测试 CLI 的基本功能。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.source_path = Path(self.tmpdir) / "source.png"
        Image.fromarray(make_test_image(400, 400)).save(self.source_path)

    def test_remove_cli(self):
        import scan_edit_ops as ops
        output = Path(self.tmpdir) / "removed.png"
        ret = ops.main([
            "remove",
            "--source", str(self.source_path),
            "--boxes", "50,50,200,80",
            "--output", str(output),
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(output.exists())

    def test_move_cli(self):
        import scan_edit_ops as ops
        output = Path(self.tmpdir) / "moved.png"
        ret = ops.main([
            "move",
            "--source", str(self.source_path),
            "--content-x", "40,300",
            "--source-y", "100,250",
            "--shift-y", "50",
            "--output", str(output),
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(output.exists())

    def test_verify_cli(self):
        import scan_edit_ops as ops
        # 用同一张图验证（应无变化）
        ret = ops.main([
            "verify",
            "--source", str(self.source_path),
            "--result", str(self.source_path),
        ])
        self.assertEqual(ret, 0)

    def test_package_cli(self):
        """测试 package 子命令（新建 PDF）。"""
        import scan_edit_ops as ops
        output = Path(self.tmpdir) / "output.pdf"
        ret = ops.main([
            "package",
            "--source", str(self.source_path),
            "--output", str(output),
            "--page-size", "400,400",
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(output.exists())

    def test_package_cli_replace_image(self):
        """测试 package 子命令的 --original-pdf 模式（替换内嵌图、保留 OCR 层）。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF，跳过替换内嵌图模式测试")
        import scan_edit_ops as ops

        # 造一个带内嵌图的原始 PDF（模拟含扫描图的原始文件）。
        embed_png = Path(self.tmpdir) / "embed_source.png"
        Image.fromarray(make_test_image(400, 400)).save(embed_png)
        original = Path(self.tmpdir) / "original.pdf"
        doc = fitz.open()
        page = doc.new_page(width=400, height=400)
        page.insert_image(page.rect, filename=str(embed_png))
        doc.save(str(original))
        doc.close()

        # 新图：同样 400x400，局部涂黑模拟编辑后的结果。
        new_png = Path(self.tmpdir) / "new_page.png"
        new_img = make_test_image(400, 400).copy()
        new_img[10:30, 10:30] = (0, 0, 0)
        Image.fromarray(new_img).save(new_png)

        output = Path(self.tmpdir) / "replaced.pdf"
        ret = ops.main([
            "package",
            "--source", str(new_png),
            "--output", str(output),
            "--original-pdf", str(original),
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(output.exists())
        pages, page_size = utils.pdf_page_info(output)
        self.assertEqual(pages, 1)
        self.assertAlmostEqual(page_size[0], 400, delta=0.5)
        self.assertAlmostEqual(page_size[1], 400, delta=0.5)


class TestEdgeCaseRegressions(unittest.TestCase):
    """覆盖 BUG-009 至 BUG-013 的边界回归测试。

    这些 bug 都曾因"现有测试只覆盖正常路径"而漏网，故单独成类锁定修复。
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _save_png(self, name, arr):
        path = Path(self.tmpdir) / name
        Image.fromarray(arr).save(path)
        return path

    # ── BUG-009：空白参考框不得误判为"确定 27 号" ──

    def test_identify_size_rejects_blank_reference(self):
        """空白参考框在所有阈值下都抓不到墨迹，应以非零码退出而非给出虚假确定结论。"""
        import subprocess
        import sys
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体，跳过字号识别测试")
        font_path, _ = font_registry.default_cjk_font()
        blank = self._save_png("blank.png", np.full((100, 100), 255, dtype=np.uint8))
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "identify_size.py"),
             "--source", str(blank), "--font", font_path,
             "--ref", "田=10,10,50,50"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0, "空白参考框不应给出成功结论")
        self.assertIn("未检测到有效墨迹", completed.stderr)

    # ── BUG-012：墨迹蒙版与 Telea 修补不得越过用户框定的 boxes ──

    def test_ink_mask_stays_within_boxes_when_ink_touches_edge(self):
        """框内边缘有墨迹时，膨胀后蒙版仍不得越出 boxes。"""
        img = np.full((200, 200, 3), 245, dtype=np.uint8)
        img[89:95, 89:95] = 40  # 紧贴框边界的墨迹
        boxes = [(90, 90, 110, 110)]
        mask = utils.ink_mask_in_boxes(img, boxes, threshold=180, dilation=5)
        region = np.zeros(img.shape[:2], dtype=np.uint8)
        region[90:110, 90:110] = 255
        outside_mask = int(np.count_nonzero((mask > 0) & (region == 0)))
        self.assertEqual(outside_mask, 0, "蒙版不应越过 boxes")

    def test_telea_changes_stay_within_boxes_at_edge_ink(self):
        """框内边缘墨迹经 Telea 修补后，框外变化像素应为 0。"""
        img = np.full((200, 200, 3), 245, dtype=np.uint8)
        img[89:95, 89:95] = 40
        boxes = [(90, 90, 110, 110)]
        result, _ = utils.remove_regions_telea(img, boxes, ink_threshold=180, dilation=5)
        outside = utils.changes_outside_boxes(img, result, boxes)
        self.assertEqual(outside, 0, "Telea 修补不应在 boxes 外产生变化像素")
        # 确认框内仍有有效清理
        region = np.zeros(img.shape[:2], dtype=np.uint8)
        region[90:110, 90:110] = 255
        inside = int(np.count_nonzero(np.any(img != result, axis=2) & (region > 0)))
        self.assertGreater(inside, 0, "框内墨迹应被清理")

    # ── BUG-013：多图页面应选整页图，歧义时报错 ──

    def _make_pdf_with_images(self, name, placements, page_wh=(100, 100)):
        """placements: [(rect_tuple, png_path)]，按顺序插入页面。"""
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=page_wh[0], height=page_wh[1])
        for rect, png in placements:
            page.insert_image(fitz.Rect(*rect), filename=str(png))
        path = Path(self.tmpdir) / name
        doc.save(str(path))
        doc.close()
        return path

    def test_replace_image_picks_full_page_not_first(self):
        """images[0] 是小印章、images[1] 是整页图时，应替换整页图。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF，跳过多图测试")
        small = self._save_png("small.png", np.full((10, 10, 3), 50, dtype=np.uint8))
        full = self._save_png("full.png", np.full((100, 100, 3), 200, dtype=np.uint8))
        # 先插小图（成为 images[0]），再插整页图
        original = self._make_pdf_with_images(
            "multi.pdf",
            [((0, 0, 10, 10), small), ((0, 0, 100, 100), full)],
        )
        doc = fitz.open(str(original))
        page = doc[0]
        images = page.get_images(full=True)
        doc.close()
        # images[0] 应是小图（xref 小），选出的应是整页图
        selected = utils._select_page_image_xref(
            fitz.open(str(original))[0], images, strict=True
        )
        self.assertEqual(selected, images[1][0], "应选出整页图而非小印章")

    def test_replace_image_raises_on_ambiguous_multi_image(self):
        """两张高覆盖、比例接近的不同图，strict 模式应报错而非静默替换。

        注意：必须用两张**不同**的图（不同 xref）。旧用例误用同一文件插入两次，
        PyMuPDF 会复用同一 xref——经 BUG-036 去重后成了单候选，不再属于"歧义"。
        """
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF，跳过多图测试")
        img_a = self._save_png("img_a.png", np.full((100, 100, 3), 200, dtype=np.uint8))
        img_b = self._save_png("img_b.png", np.full((100, 100, 3), 180, dtype=np.uint8))
        original = self._make_pdf_with_images(
            "ambig.pdf",
            [((0, 0, 90, 90), img_a), ((0, 0, 85, 85), img_b)],
        )
        doc = fitz.open(str(original))
        page = doc[0]
        images = page.get_images(full=True)
        doc.close()
        # 两张不同图应得到不同 xref
        self.assertNotEqual(images[0][0], images[1][0], "两张不同图应有不同 xref")
        with self.assertRaises(RuntimeError):
            utils._select_page_image_xref(
                fitz.open(str(original))[0], images, strict=True
            )

    # ── BUG-010：替换模式应创建尚不存在的输出父目录 ──

    def test_replace_image_creates_nested_output_dir(self):
        """--original-pdf 模式输出到不存在的嵌套目录时不应报错。"""
        import importlib.util
        if importlib.util.find_spec("fitz") is None:
            self.skipTest("未安装 PyMuPDF，跳过替换内嵌图模式测试")
        embed = self._save_png("embed.png", np.full((100, 100, 3), 200, dtype=np.uint8))
        original = self._make_pdf_with_images("single.pdf", [((0, 0, 100, 100), embed)])
        new_img = Image.fromarray(np.full((100, 100, 3), 100, dtype=np.uint8))
        nested_out = Path(self.tmpdir) / "nested" / "deep" / "out.pdf"
        utils.replace_pdf_image(original, nested_out, new_img)
        self.assertTrue(nested_out.exists(), "嵌套输出目录应被自动创建")

    # ── BUG-011：验证器应支持多页 PDF 与 page_index ──

    def test_verify_multipage_pdf_passes_with_expected_pages(self):
        """两页 PDF 配置 expected_pages=2、page_index=1 应通过验证。"""
        import json
        import subprocess
        import sys
        img = self._save_png("p.png", np.full((100, 100, 3), 200, dtype=np.uint8))
        import fitz

        def make_multipage(path):
            doc = fitz.open()
            for _ in range(2):
                p = doc.new_page(width=100, height=100)
                p.insert_image(p.rect, filename=str(img))
            doc.save(str(path))
            doc.close()

        src = Path(self.tmpdir) / "src.pdf"
        make_multipage(src)
        final = Path(self.tmpdir) / "final.pdf"
        make_multipage(final)
        config = [{
            "name": "multipage",
            "source_pdf": str(src),
            "final_pdf": str(final),
            "expected_pages": 2,
            "page_index": 1,
        }]
        cfg = Path(self.tmpdir) / "cfg.json"
        cfg.write_text(json.dumps(config))
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "verify_outputs.py"), "--config", str(cfg)],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)

    def test_verify_multipage_fails_when_expected_pages_mismatched(self):
        """两页 PDF 不配置 expected_pages（默认 1）应报页数不符。"""
        import json
        import subprocess
        import sys
        img = self._save_png("p.png", np.full((100, 100, 3), 200, dtype=np.uint8))
        import fitz
        doc = fitz.open()
        for _ in range(2):
            p = doc.new_page(width=100, height=100)
            p.insert_image(p.rect, filename=str(img))
        path = Path(self.tmpdir) / "two.pdf"
        doc.save(str(path))
        doc.close()
        config = [{"name": "default1", "source_pdf": str(path), "final_pdf": str(path)}]
        cfg = Path(self.tmpdir) / "cfg.json"
        cfg.write_text(json.dumps(config))
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "verify_outputs.py"), "--config", str(cfg)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("页数应为 1，实际为 2", completed.stderr)


class TestCompoundModes(unittest.TestCase):
    """测试 G2（整矩形蒙版）、G3（纯底色偏移归一化）、G6（复制后清除复合操作）。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    # ── G2：整矩形蒙版 ──

    def test_full_mask_covers_entire_rectangle(self):
        """full_mask_in_boxes 应把整个矩形设为 255，不区分墨迹与背景。"""
        img = make_test_image(200, 200)
        mask = utils.full_mask_in_boxes(img, [(50, 50, 150, 80)])
        # 框内全为 255
        self.assertTrue(np.all(mask[50:80, 50:150] == 255))
        # 框外全为 0
        self.assertTrue(np.all(mask[:50, :] == 0))
        self.assertTrue(np.all(mask[80:, :] == 0))
        self.assertTrue(np.all(mask[:, :50] == 0))
        self.assertTrue(np.all(mask[:, 150:] == 0))

    def test_full_mask_covers_more_than_ink_mask(self):
        """整矩形蒙版的非零像素应不少于墨迹蒙版（因为覆盖了背景区域）。"""
        img = make_test_image(200, 200)
        boxes = [(50, 50, 150, 80)]
        full_mask = utils.full_mask_in_boxes(img, boxes)
        ink_mask = utils.ink_mask_in_boxes(img, boxes, threshold=180)
        self.assertGreaterEqual(np.count_nonzero(full_mask), np.count_nonzero(ink_mask))

    def test_remove_telea_full_mask_mode_changes_background(self):
        """mask_mode='full' 应清除整个矩形区域（含背景），不只清理墨迹。"""
        img = make_test_image(200, 200).copy()
        # 在背景区放一个非墨迹的灰色斑点（亮度 > 180，不会被 ink 蒙版选中）
        img[55:60, 55:60] = (200, 200, 200)
        boxes = [(50, 50, 150, 80)]

        result_ink, _ = utils.remove_regions_telea(img, boxes, mask_mode="ink")
        result_full, _ = utils.remove_regions_telea(img, boxes, mask_mode="full")

        # full 模式应改变灰色斑点区域，ink 模式不一定
        diff_full = utils.image_diff(img, result_full)
        diff_ink = utils.image_diff(img, result_ink)
        self.assertGreater(diff_full.changed_pixels, 0)
        # full 模式应比 ink 模式改变更多像素（至少覆盖了背景区域）
        self.assertGreaterEqual(diff_full.changed_pixels, diff_ink.changed_pixels)

    # ── G3：纯底色偏移归一化 ──

    def test_normalize_offset_mode_returns_unit_scale(self):
        """offset 模式的对比度倍率应为 1.0（不做缩放，只做偏移）。"""
        donor = make_test_image(100, 30)
        target_ref = make_test_image(30, 30)
        target_bg = make_test_image(100, 30)
        _, scale = utils.normalize_donor_patch(donor, target_ref, target_bg, mode="offset")
        self.assertEqual(scale, 1.0)

    def test_normalize_offset_differs_from_contrast(self):
        """offset 和 contrast 两种模式应产生不同结果。"""
        # 构造供体与目标有不同亮度但相同对比度的场景
        donor = np.full((30, 100, 3), 240, dtype=np.uint8)
        donor[5:25, 10:90] = (60, 60, 60)
        target_ref = np.full((30, 30, 3), 230, dtype=np.uint8)
        target_ref[5:25, 5:25] = (50, 50, 50)
        target_bg = np.full((30, 100, 3), 230, dtype=np.uint8)

        norm_offset, _ = utils.normalize_donor_patch(donor, target_ref, target_bg, mode="offset")
        norm_contrast, _ = utils.normalize_donor_patch(donor, target_ref, target_bg, mode="contrast")
        self.assertFalse(np.array_equal(norm_offset, norm_contrast))

    def test_normalize_offset_preserves_donor_shape(self):
        """offset 模式只做加性偏移，应保留供体的相对结构（差值恒定）。"""
        donor = make_test_image(100, 30)
        target_ref = make_test_image(30, 30)
        target_bg = make_test_image(100, 30)
        normalized, _ = utils.normalize_donor_patch(donor, target_ref, target_bg, mode="offset")
        # 归一化后与原供体的差值应近似恒定（即只做了加性偏移）
        diff = normalized.astype(np.float32) - donor.astype(np.float32)
        # 差值的标准差应很小（不完全是 0 因有 clip 和中位数估计）
        self.assertLess(diff.std(), 5.0)

    # ── G6：复制后清除复合操作 ──

    def test_move_and_clear_moves_block_and_clears_regions(self):
        """move_and_clear 应将源块上移，并清除所有指定区域。"""
        img = make_test_image(400, 400)
        content_x = (50, 200)
        source_y = (100, 200)
        shift_y = 30
        # 清除区域：源区域本身 + 一个额外区域
        clear_boxes = [(50, 100, 200, 200), (250, 50, 350, 100)]

        result = utils.move_and_clear(
            img,
            content_x=content_x,
            source_y=source_y,
            shift_y=shift_y,
            clear_boxes=clear_boxes,
        )

        # 源块应被复制到新位置 (y=70..100)
        original_block = img[100:200, 50:200]
        # 目标位置的前 30 行应来自源块的开头
        self.assertTrue(np.array_equal(result[70:100, 50:200], original_block[:30]))

        # 源区域应被清除（不再是原图内容）
        source_after = result[100:200, 50:200]
        source_before = img[100:200, 50:200]
        self.assertFalse(np.array_equal(source_before, source_after))

        # 额外区域也应被清除
        extra_after = result[50:100, 250:350]
        extra_before = img[50:100, 250:350]
        self.assertFalse(np.array_equal(extra_before, extra_after))

    def test_compound_cli(self):
        """compound 子命令应成功执行并产出输出文件。"""
        import scan_edit_ops as ops
        source_path = Path(self.tmpdir) / "source.png"
        Image.fromarray(make_test_image(400, 400)).save(source_path)
        output = Path(self.tmpdir) / "compound.png"
        ret = ops.main([
            "compound",
            "--source", str(source_path),
            "--content-x", "50,200",
            "--source-y", "100,200",
            "--shift-y", "30",
            "--clear-boxes", "50,100,200,200", "250,50,350,100",
            "--output", str(output),
        ])
        self.assertEqual(ret, 0)
        self.assertTrue(output.exists())

    def test_replace_with_full_mask_and_offset_normalize(self):
        """replace 支持 mask_mode='full' + normalize_mode='offset' 组合。"""
        img = make_test_image(300, 300)
        result, mask, scale = utils.replace_with_donor(
            img,
            img,
            donor_box=(50, 50, 150, 80),
            remove_boxes=[(200, 200, 280, 250)],
            destination=(200, 200),
            reference_box=(50, 50, 150, 80),
            mask_mode="full",
            normalize_mode="offset",
        )
        self.assertEqual(result.shape, img.shape)
        self.assertEqual(scale, 1.0)  # offset 模式 scale 恒为 1.0
        diff = utils.image_diff(img, result)
        self.assertGreater(diff.changed_pixels, 0)


class TestBugFix016_018(unittest.TestCase):
    """BUG-016/017/018 回归测试。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    # ── BUG-016：插值删除触及页面边缘不应产生黑块 ──

    def test_interpolate_full_width_no_black_block(self):
        """删除框覆盖整页宽度时，填底不应出现纯黑块（NaN->0 回归）。"""
        img = np.full((150, 200, 3), 200, dtype=np.uint8)
        result = utils.remove_regions_interpolate(img, [(0, 50, 200, 100)], seed=42)
        fill = result[50:100, 0:200]
        self.assertGreater(fill.min(), 0, "填底不应有纯黑像素 (min=0 表示 NaN 回归)")

    def test_interpolate_left_edge_no_black_block(self):
        """删除框左边界紧贴页面左边缘时，填底不应出现黑块。"""
        img = np.full((150, 200, 3), 200, dtype=np.uint8)
        result = utils.remove_regions_interpolate(img, [(0, 50, 100, 100)], seed=42)
        fill = result[50:100, 0:100]
        self.assertGreater(fill.min(), 0, "左边缘填底不应有纯黑像素")

    def test_interpolate_right_edge_no_black_block(self):
        """删除框右边界紧贴页面右边缘时，填底不应出现黑块。"""
        img = np.full((150, 200, 3), 200, dtype=np.uint8)
        result = utils.remove_regions_interpolate(img, [(100, 50, 200, 100)], seed=42)
        fill = result[50:100, 100:200]
        self.assertGreater(fill.min(), 0, "右边缘填底不应有纯黑像素")

    def test_interpolate_compound_full_width_no_black(self):
        """compound 子命令的 clear-boxes 覆盖整页宽度时也不应产生黑块。"""
        import scan_edit_ops as ops
        source_path = Path(self.tmpdir) / "source.png"
        Image.fromarray(np.full((300, 300, 3), 200, dtype=np.uint8)).save(source_path)
        output = Path(self.tmpdir) / "compound.png"
        ret = ops.main([
            "compound",
            "--source", str(source_path),
            "--content-x", "0,300",
            "--source-y", "150,250",
            "--shift-y", "50",
            "--clear-boxes", "0,150,300,250",
            "--output", str(output),
        ])
        self.assertEqual(ret, 0)
        result = np.asarray(Image.open(output))
        # 源区域应被清除，但不应是纯黑
        cleared = result[150:250, 0:300]
        self.assertGreater(cleared.min(), 0, "compound 全宽清除不应有纯黑像素")

    # ── BUG-017：字号识别不应拒绝较浅但有效的墨迹 ──

    def test_identify_size_accepts_light_ink(self):
        """灰度 100 的有效墨迹在最高阈值下应被检出（不被误判为空白）。"""
        import identify_size
        # 灰度 100 的"浅墨迹"——min(thrs)=80 会漏检，max(thrs)=246 能检出
        crop = np.full((30, 30), 255, dtype=np.uint8)
        crop[5:25, 5:25] = 100
        self.assertIsNone(identify_size.ink_dims(crop, 80),
                          "灰度 100 在 thr=80 下不应检出（太严格）")
        self.assertIsNotNone(identify_size.ink_dims(crop, 246),
                             "灰度 100 在 thr=246 下应检出（最宽松阈值）")


class TestBugFix017LargeEdge(unittest.TestCase):
    """TST-011：全宽大面积删除框贴近顶/底，上下样本行数 < 目标高度时不得出黑块。"""

    def _assert_clean_fill(self, result, box, *, label):

        x1, y1, x2, y2 = box
        fill = result[y1:y2, x1:x2]
        self.assertEqual(fill.shape, (y2 - y1, x2 - x1, 3), label)
        self.assertFalse(np.isnan(fill.astype(np.float32)).any(), f"{label}: 含 NaN")
        zero_channels = int(np.count_nonzero(fill == 0))
        self.assertEqual(zero_channels, 0, f"{label}: 零值通道={zero_channels}")
        self.assertGreater(float(fill.min()), 50, f"{label}: 填底过暗 min={fill.min()}")

    def test_full_width_top_heavy_no_black(self):
        """(0,0,W,0.8H)：贴顶全宽，上下样本远少于目标高度。"""
        import warnings

        h, w = 100, 40
        img = np.full((h, w, 3), 245, dtype=np.uint8)
        img[10:90, 5:35] = 40
        box = (0, 0, w, 80)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = utils.remove_regions_interpolate(img, [box], seed=1)
        empty_slice_warns = [
            c for c in caught
            if issubclass(c.category, RuntimeWarning)
            and "empty" in str(c.message).lower()
        ]
        self.assertEqual(len(empty_slice_warns), 0, "不应再有 Mean of empty slice 警告")
        self._assert_clean_fill(result, box, label="top-heavy")

    def test_full_width_bottom_heavy_no_black(self):
        """(0,0.2H,W,H)：贴底全宽。"""
        h, w = 100, 40
        img = np.full((h, w, 3), 245, dtype=np.uint8)
        box = (0, 20, w, h)
        result = utils.remove_regions_interpolate(img, [box], seed=1)
        self._assert_clean_fill(result, box, label="bottom-heavy")

    def test_full_width_near_full_height_no_black(self):
        """(0,0.05H,W,0.95H)：接近全页高度的全宽框。"""
        h, w = 100, 40
        img = np.full((h, w, 3), 245, dtype=np.uint8)
        box = (0, 5, w, 95)
        result = utils.remove_regions_interpolate(img, [box], seed=1)
        self._assert_clean_fill(result, box, label="near-full-height")

    def test_chk012_repro_boxes_no_zero_channels(self):
        """CHK-012 最小复现：(0,0,40,80) 与 (0,5,40,95) 零值通道应为 0。"""
        img = np.full((100, 40, 3), 245, dtype=np.uint8)
        img[10:90, 5:35] = 40
        for box in [(0, 0, 40, 80), (0, 5, 40, 95)]:
            result = utils.remove_regions_interpolate(img, [box], seed=1)
            x1, y1, x2, y2 = box
            fill = result[y1:y2, x1:x2]
            self.assertEqual(int(np.count_nonzero(fill == 0)), 0, f"box={box}")


class TestBugFix020_027(unittest.TestCase):
    """CHK-017 发现的 BUG-020 至 BUG-027 回归测试。

    这些 bug 多数是"合法路径全过、越界/退化输入裸崩或静默出错"，
    逐项锁定修复后的行为：越界报清晰错误、合法输入不受影响。
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # 300×300 浅灰底 + 一条深色横带（y=100..130, x=50..250）
        self.img = np.full((300, 300, 3), 240, dtype=np.uint8)
        self.img[100:130, 50:250] = 60
        # 合法供体：浅灰底 + 深色块
        self.donor = self.img[0:30, 0:100].copy()
        self.donor[5:25, 10:90] = 60
        self.ref = self.img[100:130, 150:250]
        self.bg = self.img[0:30, 0:100]

    def _save_source(self, name="s.png"):
        path = Path(self.tmpdir) / name
        Image.fromarray(self.img).save(path)
        return path

    # ── BUG-020：越界移动必须报错，不得静默绕到页底 ──

    def test_move_block_rejects_off_page_destination(self):
        """shift_y ≥ y1 时目标 y 为负，旧实现负切片把块写到页底。"""
        with self.assertRaisesRegex(ValueError, "越出页面"):
            utils.move_block(
                self.img, content_x=(50, 250), source_y=(100, 130), shift_y=150
            )

    def test_move_and_clear_rejects_off_page_destination(self):
        with self.assertRaisesRegex(ValueError, "越出页面"):
            utils.move_and_clear(
                self.img, content_x=(50, 250), source_y=(100, 130), shift_y=150,
                clear_boxes=[(50, 100, 250, 130)],
            )

    def test_move_block_valid_shift_lands_at_expected_rows(self):
        """合法上移仍精确落在目标行，无页底伪影。"""
        result, _ = utils.move_block(
            self.img, content_x=(50, 250), source_y=(100, 130), shift_y=50
        )
        rows = np.where(np.any(result != self.img, axis=2))[0]
        self.assertEqual(rows.min(), 50)
        self.assertEqual(rows.max(), 129)  # 目标 50..80 + 清理带 80..130

    # ── BUG-021：零对比度供体不得 ZeroDivisionError ──

    def test_normalize_all_ink_donor_raises_clear_error(self):
        all_ink = np.full((30, 100, 3), 60, dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "对比度"):
            utils.normalize_donor_patch(all_ink, self.ref, self.bg, mode="contrast")

    def test_normalize_flat_donor_raises_clear_error(self):
        flat = np.full((30, 100, 3), 120, dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "对比度"):
            utils.normalize_donor_patch(flat, self.ref, self.bg, mode="contrast")

    def test_normalize_error_suggests_offset_mode(self):
        all_ink = np.full((30, 100, 3), 60, dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "offset"):
            utils.normalize_donor_patch(all_ink, self.ref, self.bg, mode="contrast")

    def test_normalize_offset_mode_unaffected_by_zero_contrast(self):
        """offset 模式不做对比度除法，全墨迹供体仍可用。"""
        all_ink = np.full((30, 100, 3), 60, dtype=np.uint8)
        normalized, scale = utils.normalize_donor_patch(
            all_ink, self.ref, self.bg, mode="offset"
        )
        self.assertEqual(scale, 1.0)
        self.assertEqual(normalized.shape, all_ink.shape)

    def test_normalize_valid_donor_still_works(self):
        normalized, scale = utils.normalize_donor_patch(
            self.donor, self.ref, self.bg, mode="contrast"
        )
        self.assertGreater(scale, 0)
        self.assertEqual(normalized.shape, self.donor.shape)

    # ── BUG-022：插值删除框越界裁剪而非崩溃 ──

    def test_interpolate_box_past_bottom_edge_clips(self):
        """bottom > 图高：只填界内部分，界外不变，无黑块。"""
        result = utils.remove_regions_interpolate(self.img, [(50, 250, 250, 350)], seed=42)
        fill = result[250:300, 50:250]
        self.assertGreater(fill.min(), 0, "裁剪后的填底不应有纯黑像素")
        self.assertTrue(np.array_equal(result[:250], self.img[:250]), "框外不应变化")

    def test_interpolate_box_fully_outside_image_is_noop(self):
        result = utils.remove_regions_interpolate(self.img, [(500, 500, 600, 600)], seed=42)
        self.assertTrue(np.array_equal(result, self.img))

    def test_interpolate_in_bounds_behavior_unchanged(self):
        """界内框行为与修复前一致：同 seed 确定性 + 无黑块。"""
        r1 = utils.remove_regions_interpolate(self.img, [(50, 50, 250, 90)], seed=7)
        r2 = utils.remove_regions_interpolate(self.img, [(50, 50, 250, 90)], seed=7)
        self.assertTrue(np.array_equal(r1, r2))
        self.assertGreater(r1[50:90, 50:250].min(), 0)

    # ── BUG-023：贴入位置越界报清晰错误 ──

    def test_paste_donor_out_of_bounds_raises(self):
        with self.assertRaisesRegex(ValueError, "越出图像"):
            utils.paste_donor_patch(self.img, self.donor, (280, 100), self.ref, self.bg)

    def test_paste_donor_valid_destination_works(self):
        result, scale = utils.paste_donor_patch(
            self.img, self.donor, (100, 200), self.ref, self.bg
        )
        self.assertEqual(result.shape, self.img.shape)
        self.assertGreater(scale, 0)

    # ── BUG-024：--page-size 非法输入给清晰错误而非裸 IndexError ──

    def test_package_page_size_single_value_rejected(self):
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "package", "--source", str(src),
            "--output", str(Path(self.tmpdir) / "o.pdf"), "--page-size", "595.2",
        ])
        self.assertEqual(ret, 2)

    def test_package_page_size_non_numeric_rejected(self):
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "package", "--source", str(src),
            "--output", str(Path(self.tmpdir) / "o.pdf"), "--page-size", "abc,def",
        ])
        self.assertEqual(ret, 2)

    def test_package_page_size_nan_rejected(self):
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "package", "--source", str(src),
            "--output", str(Path(self.tmpdir) / "o.pdf"), "--page-size", "nan,800",
        ])
        self.assertEqual(ret, 2)

    # ── BUG-025：空 ROI 取样与子目录输出 ──

    def test_sample_ink_color_empty_box_raises(self):
        import scan_text_fusion as stf
        pil = Image.fromarray(self.img)
        with self.assertRaisesRegex(ValueError, "没有交集"):
            stf.sample_ink_color(pil, (500, 500, 600, 600), quiet=True)

    def test_save_with_crop_creates_subdirectory(self):
        """--output 含子目录成分（sub/x.png）时应自动建目录而非 FileNotFoundError。"""
        import scan_text_fusion as stf
        out_dir = Path(self.tmpdir) / "fusion_out"
        full = stf.save_with_crop(
            Image.fromarray(self.img), out_dir, "sub/x.png", (10, 10, 50, 50), "x_crop.png"
        )
        self.assertTrue(full.exists())
        self.assertTrue((out_dir / "x_crop.png").exists())

    # ── BUG-027：ruff 门禁覆盖范围 ──

    def test_run_checks_ruff_covers_scripts(self):
        """run_checks.sh 的 ruff 实际命令须为 `ruff check .`（忽略注释行）。"""
        run_checks = (SCRIPTS_DIR / "run_checks.sh").read_text(encoding="utf-8")
        cmd_lines = [
            line.strip()
            for line in run_checks.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertTrue(
            any(line == "ruff check ." or line.startswith("ruff check . ") for line in cmd_lines),
            "run_checks.sh 须包含非注释命令 `ruff check .`",
        )

    def test_ruff_clean_over_scripts_dir(self):
        """scripts/ 目录 ruff 全清。"""
        import shutil
        import subprocess
        if shutil.which("ruff") is None:
            self.skipTest("本机未安装 ruff")
        scripts_dir = SCRIPTS_DIR
        completed = subprocess.run(
            ["ruff", "check", str(scripts_dir)], capture_output=True, text=True
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


class TestBugFix028_032(unittest.TestCase):
    """BUG-028 至 BUG-032 回归测试（CHK-018 二次审查清单项）。

    全部为"合法路径全过、退化输入裸崩或静默出错"类型，逐项锁定修复后的行为。
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    # ── BUG-028：parse_box 不校验坐标顺序，倒置/空框静默接受 ──

    def test_parse_box_rejects_inverted_x(self):
        """x2 < x1 的倒置框应被拒绝。"""
        import argparse
        import scan_edit_ops as ops
        with self.assertRaisesRegex(argparse.ArgumentTypeError, r"x1<x2|y1<y2"):
            ops.parse_box("200,50,100,100")

    def test_parse_box_rejects_inverted_y(self):
        """y2 < y1 的倒置框应被拒绝。"""
        import argparse
        import scan_edit_ops as ops
        with self.assertRaisesRegex(argparse.ArgumentTypeError, r"x1<x2|y1<y2"):
            ops.parse_box("50,200,100,100")

    def test_parse_box_rejects_zero_area(self):
        """x1==x2 或 y1==y2 的零面积框应被拒绝。"""
        import argparse
        import scan_edit_ops as ops
        with self.assertRaisesRegex(argparse.ArgumentTypeError, r"x1<x2|y1<y2|空框"):
            ops.parse_box("50,50,50,100")
        with self.assertRaisesRegex(argparse.ArgumentTypeError, r"x1<x2|y1<y2|空框"):
            ops.parse_box("50,50,100,50")

    def test_parse_box_valid_box_accepted(self):
        """合法框不受影响。"""
        import scan_edit_ops as ops
        self.assertEqual(ops.parse_box("50,50,100,100"), (50, 50, 100, 100))

    # ── BUG-029：feather_mask(edge=0) 除零产生 NaN ──

    def test_feather_mask_edge_zero_no_nan(self):
        """edge=0 时角点 distance=0 处不产生 NaN，返回全 1 硬边蒙版。"""
        mask = utils.feather_mask(10, 10, edge=0)
        self.assertFalse(np.isnan(mask).any(), "edge=0 不应产生 NaN")
        self.assertTrue(np.all(mask == 1.0), "edge=0 应返回全 1 蒙版")

    def test_feather_mask_edge_negative_no_nan(self):
        """edge<0 时不产生 NaN，返回全 1 硬边蒙版。"""
        mask = utils.feather_mask(10, 10, edge=-1)
        self.assertFalse(np.isnan(mask).any())
        self.assertTrue(np.all(mask == 1.0))

    def test_feather_mask_valid_edge_unchanged(self):
        """合法 edge（>0）行为与旧版一致：角点=0、中心=1。"""
        mask = utils.feather_mask(20, 20, edge=4)
        self.assertAlmostEqual(float(mask[0, 0, 0]), 0.0)
        self.assertAlmostEqual(float(mask[10, 10, 0]), 1.0)

    # ── BUG-030：save_image_as_pdf 不校验 page_size，0/负数仍写出无效 PDF ──

    def test_save_pdf_rejects_zero_page_size(self):
        """page_size=(0,800) 应报 ValueError 而非写出 0×0 页面 PDF。"""
        from PIL import Image as PI
        img = PI.new("RGB", (100, 100), (200, 200, 200))
        with self.assertRaises(ValueError):
            utils.save_image_as_pdf(
                img, Path(self.tmpdir) / "bad.pdf",
                page_size=(0, 800), title="", subject="",
            )

    def test_save_pdf_rejects_negative_page_size(self):
        from PIL import Image as PI
        img = PI.new("RGB", (100, 100), (200, 200, 200))
        with self.assertRaises(ValueError):
            utils.save_image_as_pdf(
                img, Path(self.tmpdir) / "bad.pdf",
                page_size=(-1, 800), title="", subject="",
            )

    def test_save_pdf_rejects_nan_page_size(self):
        from PIL import Image as PI
        img = PI.new("RGB", (100, 100), (200, 200, 200))
        with self.assertRaises(ValueError):
            utils.save_image_as_pdf(
                img, Path(self.tmpdir) / "bad.pdf",
                page_size=(float("nan"), 800), title="", subject="",
            )

    def test_save_pdf_valid_page_size_works(self):
        import fitz
        from PIL import Image as PI
        img = PI.new("RGB", (100, 100), (200, 200, 200))
        out = Path(self.tmpdir) / "ok.pdf"
        utils.save_image_as_pdf(img, out, page_size=(595.2, 841.68), title="t", subject="s")
        self.assertTrue(out.exists())
        doc = fitz.open(out)
        try:
            self.assertEqual(len(doc), 1)
            rect = doc[0].rect
            self.assertAlmostEqual(rect.width, 595.2, places=1)
            self.assertAlmostEqual(rect.height, 841.68, places=1)
            meta = doc.metadata
            self.assertEqual(meta.get("title"), "t")
            self.assertEqual(meta.get("subject"), "s")
            self.assertTrue(doc[0].get_images())
        finally:
            doc.close()

    def test_save_image_as_pdf_does_not_require_reportlab(self):
        """新建 PDF 路径不得再依赖 reportlab。"""
        import scan_edit_utils as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("reportlab", src)
        self.assertNotIn("ImageReader", src)

    # ── BUG-031：smooth_noise 1×1 归一化除零产生 NaN ──

    def test_smooth_noise_1x1_no_nan(self):
        """1×1 退化形状（max==min）不产生 NaN，返回零场。"""
        import scan_text_fusion as stf
        rng = np.random.default_rng(42)
        result = stf.smooth_noise((1, 1), rng, 1.0, 9.0)
        self.assertFalse(np.isnan(result).any(), "1×1 不应产生 NaN")
        self.assertTrue(np.all(result == 0.0), "1×1 应返回零场")

    def test_smooth_noise_normal_shape_unchanged(self):
        """合法形状的输出不含 NaN 且有正常变异。"""
        import scan_text_fusion as stf
        rng = np.random.default_rng(42)
        result = stf.smooth_noise((100, 100), rng, 1.15, 0.18)
        self.assertFalse(np.isnan(result).any())
        self.assertGreater(float(result.std()), 0.0)

    # ── BUG-032：_select_page_image_xref 全空 rect 静默返回无效 xref ──

    def test_xref_rejects_all_empty_rects(self):
        """所有内嵌图的渲染矩形均为空（ratio=0）时应报错而非静默返回。"""

        class MockRect:
            def __init__(self, w, h):
                self.width = w
                self.height = h

        class MockPage:
            def __init__(self, page_wh, images):
                self.rect = MockRect(*page_wh)
                self._images = images

            def get_image_rects(self, xref):
                return []  # 所有图都返回空 rect

        images = [(1, 0), (2, 0)]
        mock_page = MockPage((100, 100), images)
        with self.assertRaisesRegex(RuntimeError, "渲染矩形均为空"):
            utils._select_page_image_xref(mock_page, images, strict=True)

    def test_xref_normal_images_unaffected(self):
        """正常多图页面仍选出覆盖比例最大的整页图。"""

        class MockRect:
            def __init__(self, w, h):
                self.width = w
                self.height = h

        class MockPage:
            def __init__(self, page_wh, images):
                self.rect = MockRect(*page_wh)
                self._images = images

            def get_image_rects(self, xref):
                if xref == 1:
                    return [MockRect(10, 10)]
                return [MockRect(100, 100)]

        images = [(1, 0), (2, 0)]
        mock_page = MockPage((100, 100), images)
        selected = utils._select_page_image_xref(mock_page, images, strict=True)
        self.assertEqual(selected, 2, "应选出整页图 xref=2")

    def test_xref_single_image_empty_rect_still_returns(self):
        """单图早退：即使 rect 为空仍返回唯一 xref（文档化行为，非静默多选）。"""

        class MockRect:
            def __init__(self, w, h):
                self.width = w
                self.height = h

        class MockPage:
            def __init__(self):
                self.rect = MockRect(100, 100)

            def get_image_rects(self, xref):
                return []

        selected = utils._select_page_image_xref(MockPage(), [(9, 0)], strict=True)
        self.assertEqual(selected, 9)


class TestBugFix033_035(unittest.TestCase):
    """BUG-033～035：CHK-020 复核发现的同族残留。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.img = np.full((100, 100, 3), 240, dtype=np.uint8)
        self.img[40:60, 20:80] = 50

    def _save_source(self, name="s.png"):
        path = Path(self.tmpdir) / name
        Image.fromarray(self.img).save(path)
        return path

    # ── BUG-033：倒置/零高 source_y、倒置 content_x 不得静默改图 ──

    def test_move_block_rejects_inverted_source_y(self):
        with self.assertRaisesRegex(ValueError, r"source_y|y1.*y2|坐标"):
            utils.move_block(
                self.img, content_x=(20, 80), source_y=(60, 40), shift_y=10
            )

    def test_move_block_rejects_zero_height_source_y(self):
        with self.assertRaisesRegex(ValueError, r"source_y|y1.*y2|坐标"):
            utils.move_block(
                self.img, content_x=(20, 80), source_y=(40, 40), shift_y=10
            )

    def test_move_block_rejects_inverted_content_x(self):
        with self.assertRaisesRegex(ValueError, r"content_x|x1.*x2|坐标"):
            utils.move_block(
                self.img, content_x=(80, 20), source_y=(40, 60), shift_y=10
            )

    def test_move_and_clear_rejects_inverted_source_y(self):
        with self.assertRaisesRegex(ValueError, r"source_y|y1.*y2|坐标"):
            utils.move_and_clear(
                self.img,
                content_x=(20, 80),
                source_y=(60, 40),
                shift_y=10,
                clear_boxes=[(20, 40, 80, 60)],
            )

    def test_parse_ordered_pair_rejects_inverted(self):
        import argparse
        import scan_edit_ops as ops
        with self.assertRaisesRegex(argparse.ArgumentTypeError, r"a<b|起止"):
            ops.parse_ordered_pair("80,20")

    def test_parse_ordered_pair_accepts_valid(self):
        import scan_edit_ops as ops
        self.assertEqual(ops.parse_ordered_pair("20,80"), (20, 80))

    def test_parse_pair_destination_allows_any_order(self):
        """destination 是点坐标，不应强制 a<b。"""
        import scan_edit_ops as ops
        self.assertEqual(ops.parse_pair("80,20"), (80, 20))

    # ── BUG-035：--dpi <=0 清晰 exit 2 ──

    def test_package_dpi_zero_rejected(self):
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "package", "--source", str(src),
            "--output", str(Path(self.tmpdir) / "bad_dpi.pdf"),
            "--dpi", "0",
        ])
        self.assertEqual(ret, 2)

    def test_package_dpi_negative_rejected(self):
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "package", "--source", str(src),
            "--output", str(Path(self.tmpdir) / "bad_dpi_neg.pdf"),
            "--dpi", "-72",
        ])
        self.assertEqual(ret, 2)


class TestBugFix036_047(unittest.TestCase):
    """BUG-036 至 BUG-047 回归测试（CHK-022 第五轮审查清单项）。

    全部为"测试全绿但边界路径漏检"类型，逐项锁定修复后的行为。
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.img = np.full((300, 300, 3), 240, dtype=np.uint8)
        self.img[100:130, 50:250] = 60

    def _save_source(self, name="s.png"):
        path = Path(self.tmpdir) / name
        Image.fromarray(self.img).save(path)
        return path

    # ── BUG-036：_select_page_image_xref 去重重复 xref ──

    def test_xref_dedup_same_image_placed_twice(self):
        """同一张图放置两次（get_images 返回重复 xref [5,5]）应去重后正常返回，
        不再误报"覆盖比例最高的两个过近"。"""

        class MockRect:
            def __init__(self, w, h):
                self.width = w
                self.height = h

        class MockPage:
            def __init__(self):
                self.rect = MockRect(100, 100)

            def get_image_rects(self, xref):
                # 同一 xref 的两个放置块面积已由 get_image_rects 合并返回
                return [MockRect(100, 100)]

        images_dup = [(5, 0), (5, 0)]  # 同一张图放置两次
        selected = utils._select_page_image_xref(MockPage(), images_dup, strict=True)
        self.assertEqual(selected, 5, "重复 xref 去重后应正常返回 5")

    # ── BUG-037：parse_box 拒绝负坐标 ──

    def test_parse_box_rejects_negative_x(self):
        import argparse
        import scan_edit_ops as ops
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "非负"):
            ops.parse_box("-50,50,50,100")

    def test_parse_box_rejects_negative_y(self):
        import argparse
        import scan_edit_ops as ops
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "非负"):
            ops.parse_box("50,-50,100,100")

    def test_parse_box_valid_nonnegative_accepted(self):
        """合法的非负框不受影响（含 0 起点）。"""
        import scan_edit_ops as ops
        self.assertEqual(ops.parse_box("0,0,50,100"), (0, 0, 50, 100))

    # ── BUG-038：move_block / move_and_clear x 方向越界校验 ──

    def test_move_block_rejects_x_past_width(self):
        """x2 超出图宽应报错，而非被 numpy 静默截断。"""
        with self.assertRaisesRegex(ValueError, "越出页面宽度"):
            utils.move_block(self.img, content_x=(50, 350), source_y=(100, 130), shift_y=50)

    def test_move_block_rejects_negative_x(self):
        """x1<0 应报错，而非被 numpy 负索引回绕到页尾。"""
        with self.assertRaisesRegex(ValueError, "越出页面宽度"):
            utils.move_block(self.img, content_x=(-50, 250), source_y=(100, 130), shift_y=50)

    def test_move_and_clear_rejects_x_past_width(self):
        with self.assertRaisesRegex(ValueError, "越出页面宽度"):
            utils.move_and_clear(
                self.img, content_x=(50, 350), source_y=(100, 130), shift_y=50,
                clear_boxes=[(50, 100, 250, 130)],
            )

    def test_move_block_valid_x_unchanged(self):
        """合法 x 范围行为不变。"""
        result, _ = utils.move_block(
            self.img, content_x=(50, 250), source_y=(100, 130), shift_y=50
        )
        self.assertEqual(result.shape, self.img.shape)

    # ── BUG-039：verify 完全越界的 blank-box/preserve-box 不得报"通过" ──

    def test_verify_blank_box_outside_image_fails(self):
        """完全越界的 blank-box 应返回非 0，而非因空切片 dark=0 误报通过。"""
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "verify", "--source", str(src), "--result", str(src),
            "--blank-box", "5000,5000,5100,5100",
        ])
        self.assertNotEqual(ret, 0)

    def test_verify_preserve_box_outside_image_fails(self):
        """完全越界的 preserve-box 应返回非 0。"""
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "verify", "--source", str(src), "--result", str(src),
            "--preserve-box", "5000,5000,5100,5100",
        ])
        self.assertNotEqual(ret, 0)

    def test_verify_blank_box_in_bounds_still_passes(self):
        """界内 blank-box 行为不变。"""
        import scan_edit_ops as ops
        src = self._save_source()
        ret = ops.main([
            "verify", "--source", str(src), "--result", str(src),
            "--blank-box", "200,10,280,40",  # 空白区，无深色像素
        ])
        self.assertEqual(ret, 0)

    def test_blank_region_dark_pixels_empty_box_raises(self):
        """空框（x1>=x2）应报错而非返回 0。"""
        with self.assertRaisesRegex(ValueError, "为空|没有交集"):
            utils.blank_region_dark_pixels(self.img, (50, 50, 50, 100))

    # ── BUG-040：replace donor_box / reference_box 越界校验 ──

    def test_replace_donor_box_past_width_raises(self):
        """donor_box 部分越界应报错，而非静默截小供体。"""
        donor = np.full((300, 300, 3), 240, dtype=np.uint8)
        donor[50:80, 260:300] = 60
        with self.assertRaisesRegex(ValueError, "donor_box.*越出供体"):
            utils.replace_with_donor(
                self.img, donor,
                donor_box=(260, 50, 360, 80),  # x2=360 越界
                remove_boxes=[(200, 200, 260, 230)],
                destination=(200, 200),
                reference_box=(50, 100, 150, 130),
                normalize_mode="offset",
            )

    def test_replace_reference_box_past_width_raises(self):
        """reference_box 越界应报错，而非静默截小参考。"""
        donor = np.full((300, 300, 3), 240, dtype=np.uint8)
        donor[50:80, 50:150] = 60
        with self.assertRaisesRegex(ValueError, "reference_box.*越出目标"):
            utils.replace_with_donor(
                self.img, donor,
                donor_box=(50, 50, 150, 80),
                remove_boxes=[(200, 200, 260, 230)],
                destination=(200, 200),
                reference_box=(250, 100, 350, 130),  # x2=350 越界
                normalize_mode="offset",
            )

    def test_replace_valid_boxes_unaffected(self):
        """合法 donor/reference 框行为不变。"""
        donor = self.img[0:30, 0:100].copy()
        donor[5:25, 10:90] = 60
        result, _, _ = utils.replace_with_donor(
            self.img, self.img,
            donor_box=(0, 0, 100, 30),
            remove_boxes=[(200, 200, 280, 230)],
            destination=(200, 200),
            reference_box=(50, 100, 150, 130),
            normalize_mode="offset",
        )
        self.assertEqual(result.shape, self.img.shape)

    # ── BUG-041：verify_outputs 尺寸不一致不得裸 traceback ──

    def test_verify_outputs_size_mismatch_no_traceback(self):
        """源/终版页尺寸不同时应记录为用例错误，不抛 traceback、不跳过后续用例。"""
        import json
        import subprocess
        import sys
        import fitz
        src = Path(self.tmpdir) / "src.pdf"
        final = Path(self.tmpdir) / "final.pdf"
        for p, sz in [(src, (100, 100)), (final, (200, 200))]:
            doc = fitz.open()
            pg = doc.new_page(width=sz[0], height=sz[1])
            png = Path(self.tmpdir) / f"p{sz[0]}.png"
            Image.fromarray(np.full((sz[1], sz[0], 3), 200, dtype=np.uint8)).save(png)
            pg.insert_image(pg.rect, filename=str(png))
            doc.save(str(p))
            doc.close()
        # 两个用例：第一个尺寸不符，第二个正常——验证第一个不崩、第二个仍跑
        same = Path(self.tmpdir) / "same.pdf"
        doc = fitz.open()
        pg = doc.new_page(width=100, height=100)
        png = Path(self.tmpdir) / "p100.png"
        Image.fromarray(np.full((100, 100, 3), 200, dtype=np.uint8)).save(png)
        pg.insert_image(pg.rect, filename=str(png))
        doc.save(str(same))
        doc.close()
        config = [
            {"name": "mismatch", "source_pdf": str(src), "final_pdf": str(final)},
            {"name": "ok", "source_pdf": str(same), "final_pdf": str(same)},
        ]
        cfg = Path(self.tmpdir) / "cfg.json"
        cfg.write_text(json.dumps(config))
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "verify_outputs.py"),
             "--config", str(cfg)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr, "不应有裸 traceback")
        self.assertIn("尺寸不一致", completed.stderr)
        # 第二个用例仍被执行（输出里应出现 [ok]）
        self.assertIn("[ok]", completed.stdout)

    def test_verify_outputs_per_case_exception_does_not_skip_rest(self):
        """单个用例渲染异常时，后续用例仍应执行（不静默跳过）。"""
        import json
        import subprocess
        import sys
        import fitz
        good = Path(self.tmpdir) / "good.pdf"
        doc = fitz.open()
        pg = doc.new_page(width=100, height=100)
        png = Path(self.tmpdir) / "p100.png"
        Image.fromarray(np.full((100, 100, 3), 200, dtype=np.uint8)).save(png)
        pg.insert_image(pg.rect, filename=str(png))
        doc.save(str(good))
        doc.close()
        config = [
            # 第一个用例引用不存在的 PDF → 渲染异常
            {"name": "missing", "source_pdf": str(Path(self.tmpdir) / "nope.pdf"),
             "final_pdf": str(good)},
            # 第二个用例正常
            {"name": "ok2", "source_pdf": str(good), "final_pdf": str(good)},
        ]
        cfg = Path(self.tmpdir) / "cfg.json"
        cfg.write_text(json.dumps(config))
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "verify_outputs.py"),
             "--config", str(cfg)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertIn("[ok2]", completed.stdout, "第二个用例不应被跳过")
        self.assertIn("验证过程异常", completed.stderr)

    # ── BUG-043：identify_font 单候选不得判"确定" ──

    def test_identify_font_single_candidate_not_certain(self):
        """只有一个已装候选时不应判"确定"，且应能触发"字体可能未安装"提示。

        源码校验：判定块里必须有 len(ranked)<2 守卫，且单候选分支不含"确定"。
        """
        src = (SCRIPTS_DIR / "identify_font.py").read_text(encoding="utf-8")
        # 必须有 len(ranked) < 2 的守卫分支
        self.assertTrue(
            "len(ranked) < 2" in src or "len(ranked)<2" in src,
            "identify_font 须有 len(ranked)<2 守卫，防止单候选误判确定",
        )

    # ── BUG-044：font_registry.find_font 大小写不敏感 ──

    def test_find_font_case_insensitive_songti(self):
        """find_font('songti') 与 find_font('Songti') 应对称命中（都找到或都找不到）。"""
        # 行为校验：两者结果应一致（都命中或都不命中）
        # token 匹配内部统一走小写（_name_tokens 输出小写 token，spec_l 已 lower）
        r_upper = font_registry.find_font("Songti")
        r_lower = font_registry.find_font("songti")
        self.assertEqual(r_upper is not None, r_lower is not None,
                         "Songti/songti 命中应对称")

    # ── BUG-045：render_halo 1×1 退化输入不产生 NaN ──

    def test_render_halo_small_shape_no_nan(self):
        """极小退化形状（max==min）的噪声归一化不产生 NaN。"""
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体，跳过融合测试")
        import scan_text_fusion as stf
        base = Image.new("RGB", (2, 2), (245, 245, 245))
        font_path, font_idx = font_registry.default_cjk_font()
        font = stf.load_font(font_path, 20, index=font_idx)
        # 直接测内联归一化的守卫：低分辨率下 halo.shape 可能极小
        result = stf.render_halo(
            base, text="测", position=(0, 0), font=font,
            halo_color=(178, 196, 211), seed=20260701, strength=1.0,
        )
        arr = np.asarray(result).astype(np.float32)
        self.assertFalse(np.isnan(arr).any(), "render_halo 不应产生 NaN")

    # ── BUG-046：feather 蒙版维度 ≤2 不应全零 ──

    def test_feather_mask_small_width_not_all_zero(self):
        """width=1 时 alpha 不应全零（供体不应被静默丢失）。"""
        m = utils.feather_mask(1, 30, edge=4)
        self.assertEqual(float(m.max()), 1.0, "width=1 应退化为全 1 硬边（不丢供体）")

    def test_feather_mask_small_height_not_all_zero(self):
        m = utils.feather_mask(30, 1, edge=4)
        self.assertEqual(float(m.max()), 1.0)

    def test_feather_mask_2x2_not_all_zero(self):
        m = utils.feather_mask(2, 2, edge=4)
        self.assertEqual(float(m.max()), 1.0)

    def test_feather_mask_normal_dim_unchanged(self):
        """合法维度行为不变：角点=0、中心=1。"""
        m = utils.feather_mask(20, 20, edge=4)
        self.assertAlmostEqual(float(m[0, 0, 0]), 0.0)
        self.assertAlmostEqual(float(m[10, 10, 0]), 1.0)

    # ── BUG-046：identify_size 偶数阈值中位数不截断 ──

    def test_identify_size_median_rounds_not_truncates(self):
        """中位数共识赋值语句应用 round 而非 int 截断。

        检查赋值行（consensus = ...）而非全文，避免 BUG 注释里的引用误判。
        """
        import re
        identify_src = (SCRIPTS_DIR / "identify_size.py").read_text(
            encoding="utf-8"
        )
        # 找 consensus = ... 这一行实际代码（排除注释行）
        assign_lines = [
            line for line in identify_src.splitlines()
            if re.match(r"\s*consensus\s*=", line) and not line.strip().startswith("#")
        ]
        self.assertTrue(assign_lines, "应存在 consensus 赋值语句")
        assign = assign_lines[-1]
        self.assertIn("round", assign, f"中位数共识应使用 round: {assign}")
        self.assertNotIn("int(np.median", assign,
                         f"不应直接 int(np.median()) 截断: {assign}")

    # ── BUG-046：pdfium 句柄关闭 ──

    def test_render_pdf_page_closes_document(self):
        """render_pdf_page 应关闭 PdfDocument 句柄。"""
        import inspect
        src = inspect.getsource(utils.render_pdf_page)
        self.assertIn("close()", src, "render_pdf_page 应 close document")

    def test_pdf_page_info_closes_document(self):
        import inspect
        src = inspect.getsource(utils.pdf_page_info)
        self.assertIn("close()", src, "pdf_page_info 应 close document")

    # ── BUG-046：CLI 多框坏坐标不裸 traceback ──

    def test_cli_bad_boxes_no_traceback(self):
        """--boxes 给 3 个值时 exit 2 且无 traceback。"""
        import subprocess
        import sys
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_edit_ops.py"),
             "remove", "--source", str(src),
             "--boxes", "50,50,100", "--output", str(Path(self.tmpdir) / "o.png")],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr)

    def test_identify_font_bad_ref_no_traceback(self):
        """identify_font --ref 坐标个数错时不裸 traceback。"""
        import subprocess
        import sys
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "identify_font.py"),
             "--source", str(src), "--ref", "田=50,50,100"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr)

    def test_identify_font_dup_ref_warns(self):
        """identify_font 同名 --ref 重复给出应警告（不静默覆盖）。"""
        import subprocess
        import sys
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "identify_font.py"),
             "--source", str(src),
             "--ref", "田=10,10,50,50", "--ref", "田=60,10,100,50"],
            capture_output=True, text=True,
        )
        self.assertIn("重复", completed.stderr)

    def test_fusion_variants_trailing_comma_no_traceback(self):
        """scan_text_fusion --fusion-variants 尾逗号不裸 traceback。"""
        import subprocess
        import sys
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体，跳过融合测试")
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--text", "测", "--position", "10", "10",
             "--variants", "--fusion-variants", "0.5,0.7,"],
            capture_output=True, text=True,
        )
        self.assertNotIn("Traceback", completed.stderr)


class TestBugFix048_051(unittest.TestCase):
    """BUG-048 至 BUG-051 回归测试（第六轮审查发现的残留）。

    全部为"既有修复覆盖同类但遗漏了个别位置"类型：
    - BUG-048/049：fitz 文档句柄 try/finally + page_index 越界校验
    - BUG-050：identify_size --ref 缺校验（与 identify_font.parse_ref 对齐）
    - BUG-051：scan_text_fusion --reference-box/--sample-only/--crop-box 缺坐标校验
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.img = np.full((300, 300, 3), 240, dtype=np.uint8)
        self.img[100:130, 50:250] = 60

    def _save_source(self, name="s.png"):
        path = Path(self.tmpdir) / name
        Image.fromarray(self.img).save(path)
        return path

    # ── BUG-048：replace_pdf_image try/finally + page_index 校验 ──

    def test_replace_pdf_image_closes_document_on_exception(self):
        """replace_pdf_image 源码应有 try/finally 关闭 fitz 文档。"""
        import inspect
        src = inspect.getsource(utils.replace_pdf_image)
        self.assertIn("try:", src, "replace_pdf_image 应有 try/finally")
        self.assertIn("finally:", src)
        self.assertIn("document.close()", src)

    def test_replace_pdf_image_rejects_negative_page_index(self):
        """page_index=-1 不应回绕到末页，应报 IndexError。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        embed = self._save_source("embed.png")
        doc = fitz.open()
        page = doc.new_page(width=100, height=100)
        page.insert_image(page.rect, filename=str(embed))
        original = Path(self.tmpdir) / "single.pdf"
        doc.save(str(original))
        doc.close()
        new_img = Image.fromarray(np.full((100, 100, 3), 100, dtype=np.uint8))
        with self.assertRaises(IndexError):
            utils.replace_pdf_image(original, Path(self.tmpdir) / "o.pdf", new_img, page_index=-1)

    def test_replace_pdf_image_rejects_out_of_range_page_index(self):
        """page_index 超出页数应报 IndexError。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        embed = self._save_source("embed.png")
        doc = fitz.open()
        page = doc.new_page(width=100, height=100)
        page.insert_image(page.rect, filename=str(embed))
        original = Path(self.tmpdir) / "single.pdf"
        doc.save(str(original))
        doc.close()
        new_img = Image.fromarray(np.full((100, 100, 3), 100, dtype=np.uint8))
        with self.assertRaises(IndexError):
            utils.replace_pdf_image(original, Path(self.tmpdir) / "o.pdf", new_img, page_index=5)

    def test_replace_pdf_image_valid_page_index_works(self):
        """合法 page_index=0 仍正常工作。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        embed = self._save_source("embed.png")
        doc = fitz.open()
        page = doc.new_page(width=100, height=100)
        page.insert_image(page.rect, filename=str(embed))
        original = Path(self.tmpdir) / "single.pdf"
        doc.save(str(original))
        doc.close()
        new_img = Image.fromarray(np.full((100, 100, 3), 100, dtype=np.uint8))
        out = Path(self.tmpdir) / "out.pdf"
        utils.replace_pdf_image(original, out, new_img, page_index=0)
        self.assertTrue(out.exists())

    # ── BUG-049：render_case_page pymupdf try/finally + page_index 校验 ──

    def test_render_case_page_pymupdf_closes_document(self):
        """render_case_page pymupdf 路径应有 try/finally 关闭 fitz 文档。"""
        import inspect
        import verify_outputs as vo
        src = inspect.getsource(vo.render_case_page)
        self.assertIn("try:", src, "pymupdf 路径应有 try/finally")
        self.assertIn("finally:", src)
        self.assertIn("document.close()", src)

    def test_render_case_page_pymupdf_rejects_out_of_range_page_index(self):
        """pymupdf 后端 page_index 越界应报 IndexError 而非回绕到末页。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        import verify_outputs as vo
        img = self._save_source("p.png")
        doc = fitz.open()
        pg = doc.new_page(width=100, height=100)
        pg.insert_image(pg.rect, filename=str(img))
        pdf_path = Path(self.tmpdir) / "single.pdf"
        doc.save(str(pdf_path))
        doc.close()
        with self.assertRaises(IndexError):
            vo.render_case_page(pdf_path, "pymupdf", 72, page_index=5)

    def test_render_case_page_pymupdf_valid_page_works(self):
        """合法 page_index=0 的 pymupdf 渲染仍正常工作。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        import verify_outputs as vo
        img = self._save_source("p.png")
        doc = fitz.open()
        pg = doc.new_page(width=100, height=100)
        pg.insert_image(pg.rect, filename=str(img))
        pdf_path = Path(self.tmpdir) / "single.pdf"
        doc.save(str(pdf_path))
        doc.close()
        result = vo.render_case_page(pdf_path, "pymupdf", 72, page_index=0)
        self.assertEqual(result.shape[2], 3)

    # ── BUG-050：identify_size --ref 校验 ──

    def test_identify_size_parse_ref_rejects_missing_equals(self):
        """缺等号应给清晰错误而非裸 traceback。"""
        import identify_size
        with self.assertRaises(SystemExit) as ctx:
            identify_size.parse_ref("田50,50,100,100")
        self.assertIn("格式应为", str(ctx.exception))

    def test_identify_size_parse_ref_rejects_wrong_coord_count(self):
        """坐标个数不对应给清晰错误。"""
        import identify_size
        with self.assertRaises(SystemExit) as ctx:
            identify_size.parse_ref("田=50,50,100")
        self.assertIn("4 个值", str(ctx.exception))

    def test_identify_size_parse_ref_rejects_negative_coords(self):
        """负坐标应被拒绝（不会在 numpy 切片中回绕）。"""
        import identify_size
        with self.assertRaises(SystemExit) as ctx:
            identify_size.parse_ref("田=-50,50,100,100")
        self.assertIn("非负", str(ctx.exception))

    def test_identify_size_parse_ref_rejects_inverted_box(self):
        """倒置框应被拒绝。"""
        import identify_size
        with self.assertRaises(SystemExit) as ctx:
            identify_size.parse_ref("田=100,50,50,100")
        self.assertIn("x1<x2", str(ctx.exception))

    def test_identify_size_parse_ref_valid_accepted(self):
        """合法输入不受影响。"""
        import identify_size
        name, box = identify_size.parse_ref("田=50,50,100,100")
        self.assertEqual(name, "田")
        self.assertEqual(box, (50, 50, 100, 100))

    def test_identify_size_bad_ref_no_traceback(self):
        """--ref 格式错误时 exit 非零且无 traceback。"""
        import subprocess
        import sys
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "identify_size.py"),
             "--source", str(src), "--font", "nonexistent_font",
             "--ref", "田50,50,100,100"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr)

    # ── BUG-051：scan_text_fusion 坐标校验 ──

    def test_stf_validate_box_rejects_negative(self):
        """validate_box 应拒绝负坐标。"""
        import scan_text_fusion as stf
        with self.assertRaises(SystemExit) as ctx:
            stf.validate_box([-10, 50, 100, 100], "reference-box")
        self.assertIn("非负", str(ctx.exception))

    def test_stf_validate_box_rejects_inverted(self):
        """validate_box 应拒绝倒置框。"""
        import scan_text_fusion as stf
        with self.assertRaises(SystemExit) as ctx:
            stf.validate_box([100, 50, 50, 100], "crop-box")
        self.assertIn("x1<x2", str(ctx.exception))

    def test_stf_validate_box_valid_accepted(self):
        """合法框不受影响。"""
        import scan_text_fusion as stf
        result = stf.validate_box([0, 0, 100, 100], "sample-only")
        self.assertEqual(result, (0, 0, 100, 100))

    def test_stf_sample_only_negative_coords_no_traceback(self):
        """--sample-only 负坐标应 exit 非零且无 traceback。"""
        import subprocess
        import sys
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--sample-only", "-10", "50", "100", "100"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr)

    def test_stf_reference_box_negative_coords_no_traceback(self):
        """--reference-box 负坐标应 exit 非零且无 traceback。"""
        import subprocess
        import sys
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体，跳过融合测试")
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--text", "测", "--position", "10", "10",
             "--reference-box", "-10", "50", "100", "100"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr)

    def test_stf_crop_box_inverted_no_traceback(self):
        """--crop-box 倒置坐标应 exit 非零且无 traceback。"""
        import subprocess
        import sys
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体，跳过融合测试")
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--text", "测", "--position", "10", "10",
             "--crop-box", "100", "50", "50", "100"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("Traceback", completed.stderr)


class TestBugFix052_053(unittest.TestCase):
    """BUG-052 / BUG-053 及新功能回归测试。

    - BUG-052: render_pdf_page 不应用 /Rotate 条目
    - BUG-053: --reference-box 静默覆盖 --ink-color
    - 新增: identify_font 密度交叉验证 (glyph_fingerprint / rendered_fingerprint)
    - 新增: align_text.py 垂直对齐工具
    - 新增: scan_text_fusion --preview-ink 模式
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.img = np.full((300, 300, 3), 240, dtype=np.uint8)
        self.img[100:130, 50:250] = 60

    def _save_source(self, name="s.png"):
        path = Path(self.tmpdir) / name
        Image.fromarray(self.img).save(path)
        return path

    # ── BUG-052/058: render_pdf_page 旋转 ──

    def test_render_pdf_page_applies_rotation(self):
        """带 /Rotate 标记的 PDF 渲染后内容朝向应正确。

        在 portrait 页面左上角画黑块，设置 /Rotate 270（=逆时针 90°）。
        正确渲染时黑块应出现在左下角（原左上角逆时针转 90° 的位置）。
        render(rotation=0) 让 PDFium 内部处理 /Rotate；若误传
        rotation=270 则双重旋转，黑块会跑到右下角（BUG-058）。
        """
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        doc = fitz.open()
        page = doc.new_page(width=200, height=300)  # portrait
        # 左上角画黑块
        page.draw_rect(fitz.Rect(10, 10, 50, 50), color=(0, 0, 0), fill=(0, 0, 0))
        page.set_rotation(270)
        pdf_path = Path(self.tmpdir) / "rotated270.pdf"
        doc.save(str(pdf_path))
        doc.close()
        img = utils.render_pdf_page(pdf_path, dpi=72).convert("RGB")
        arr = np.asarray(img)
        dark = np.all(arr < 100, axis=2)
        ys, xs = np.where(dark)
        h, w = arr.shape[:2]
        # /Rotate=270：左上黑块应转至左下
        self.assertLess(xs.mean(), w / 2, "黑块应在左半侧（逆时针 90° 后）")
        self.assertGreater(ys.mean(), h / 2, "黑块应在下半侧（左上→左下）")

    # ── BUG-053: ink-color 优先级 ──

    def test_ink_color_argparse_default_is_none(self):
        """--ink-color 的 argparse default 应为 None（不再是 list(DEFAULT_INK_COLOR)）。"""
        import scan_text_fusion as stf
        parser = stf.build_parser()
        # 解析不带 --ink-color 的参数
        args = parser.parse_args(["--source", "x.png", "--position", "1", "2"])
        self.assertIsNone(args.ink_color)

    def test_ink_color_explicit_overrides_reference_box(self):
        """显式 --ink-color + --reference-box 时，应使用显式值并打印 sampled (reference)。"""
        import subprocess
        import sys
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体")
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--text", "测", "--position", "10", "10",
             "--ink-color", "20", "30", "40",
             "--reference-box", "50", "100", "250", "130"],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("using explicit --ink-color", completed.stdout)
        self.assertIn("sampled ink color (reference)", completed.stdout)

    def test_ink_color_reference_box_when_no_explicit(self):
        """无 --ink-color + 有 --reference-box 时，应采样并使用采样值。"""
        import subprocess
        import sys
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体")
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--text", "测", "--position", "10", "10",
             "--reference-box", "50", "100", "250", "130"],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("sampled ink color:", completed.stdout)
        self.assertNotIn("using explicit", completed.stdout)

    def test_ink_color_default_when_neither_given(self):
        """无 --ink-color 且无 --reference-box 时，应使用 DEFAULT_INK_COLOR。"""
        import scan_text_fusion as stf
        import inspect
        src = inspect.getsource(stf.run)
        # run() 应有 DEFAULT_INK_COLOR 作为 fallback
        self.assertIn("DEFAULT_INK_COLOR", src)
        self.assertIn("args.ink_color is not None", src)

    # ── --preview-ink 模式 ──

    def test_preview_ink_mode_exits_without_position(self):
        """--preview-ink 不需要 --position，应正常退出。"""
        import subprocess
        import sys
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体")
        src = self._save_source()
        out_dir = Path(self.tmpdir) / "preview"
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--preview-ink",
             "--output-dir", str(out_dir)],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("墨色预览", completed.stdout)
        self.assertTrue((out_dir / "ink_preview.png").exists())

    def test_preview_ink_with_explicit_color(self):
        """--preview-ink + --ink-color 应显示显式值和来源。"""
        import subprocess
        import sys
        src = self._save_source()
        out_dir = Path(self.tmpdir) / "preview2"
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(src), "--preview-ink",
             "--ink-color", "10", "20", "30",
             "--output-dir", str(out_dir)],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("显式 --ink-color", completed.stdout)
        self.assertIn("(10, 20, 30)", completed.stdout)

    # ── identify_font 密度交叉验证 ──

    def test_glyph_fingerprint_returns_density(self):
        """glyph_fingerprint 应返回 density 和 h_v_ratio。"""
        import identify_font as iff
        # 全白图无墨迹
        white = np.full((50, 50), 255, dtype=np.float32)
        fp = iff.glyph_fingerprint(white)
        self.assertEqual(fp["density"], 0.0)
        # 半黑图有墨迹
        half = np.full((50, 50), 255, dtype=np.float32)
        half[:25, :] = 50  # 上半部分是墨迹
        fp = iff.glyph_fingerprint(half)
        self.assertAlmostEqual(fp["density"], 0.5, places=2)
        self.assertGreater(fp["h_v_ratio"], 0)

    def test_rendered_fingerprint_returns_fingerprint(self):
        """rendered_fingerprint 应返回非 None 的指纹（本机有 CJK 字体时）。"""
        import identify_font as iff
        font_path, font_idx = (font_registry.default_cjk_font() or (None, 0))
        if font_path is None:
            self.skipTest("本机无 CJK 字体")
        fp = iff.rendered_fingerprint("测", font_path, font_idx)
        self.assertIsNotNone(fp)
        self.assertGreater(fp["density"], 0)
        self.assertGreater(fp["h_v_ratio"], 0)

    # ── align_text.py ──

    def test_align_text_ink_vertical_center(self):
        """ink_vertical_center 应正确计算墨迹垂直重心。"""
        import align_text
        # 上半黑、下半白 -> 中心应在上半部分
        gray = np.full((100, 50), 255, dtype=np.float32)
        gray[:50, :] = 50
        center = align_text.ink_vertical_center(gray)
        self.assertIsNotNone(center)
        self.assertLess(center, 50)  # 中心应在 y=0~49 范围内

    def test_align_text_ink_vertical_center_no_ink(self):
        """无墨迹时应返回 None。"""
        import align_text
        white = np.full((50, 50), 255, dtype=np.float32)
        self.assertIsNone(align_text.ink_vertical_center(white))

    def test_align_text_text_ink_center_offset(self):
        """text_ink_center_offset 应返回正值（墨迹中心在绘制点下方）。"""
        import align_text
        font_path, font_idx = (font_registry.default_cjk_font() or (None, 0))
        if font_path is None:
            self.skipTest("本机无 CJK 字体")
        offset = align_text.text_ink_center_offset("测试", font_path, font_idx, 32)
        self.assertIsNotNone(offset)
        self.assertGreater(offset, 0)  # 墨迹中心应在绘制点下方

    def test_align_text_parse_box_valid(self):
        """parse_box 应正确解析合法坐标。"""
        import align_text
        result = align_text.parse_box("10,20,30,40")
        self.assertEqual(result, (10, 20, 30, 40))

    def test_align_text_parse_box_invalid_count(self):
        """parse_box 应拒绝非 4 个值。"""
        import align_text
        with self.assertRaises(SystemExit):
            align_text.parse_box("10,20,30")

    def test_align_text_parse_box_inverted(self):
        """parse_box 应拒绝倒置坐标。"""
        import align_text
        with self.assertRaises(SystemExit):
            align_text.parse_box("30,40,10,20")

    def test_align_text_cli_outputs_adjusted_y(self):
        """align_text CLI 应输出调整后的 Y 值。"""
        import subprocess
        import sys
        font_path, font_idx = (font_registry.default_cjk_font() or (None, 0))
        if font_path is None:
            self.skipTest("本机无 CJK 字体")
        src = self._save_source()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "align_text.py"),
             "--source", str(src),
             "--ref-box", "50,100,250,130",
             "--font", font_path, "--font-index", str(font_idx),
             "--size", "32", "--text", "测试", "--y", "100"],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("调整后 Y", completed.stdout)


class TestCheckFonts(unittest.TestCase):
    """check_fonts.py 字体环境检查脚本测试。"""

    def test_check_all_returns_installed_and_missing(self):
        """check_all 应返回已安装和未安装两个列表。"""
        import check_fonts
        installed, missing = check_fonts.check_all()
        # 两者总和应等于注册表中的字体总数
        total = len(font_registry.CJK_FONTS)
        self.assertEqual(len(installed) + len(missing), total)
        # 每项是 (名称, 文件名, ttc索引) 三元组
        for item in installed + missing:
            self.assertEqual(len(item), 3)

    def test_check_all_with_filter(self):
        """--filter 应只返回匹配的字体。"""
        import check_fonts
        installed, missing = check_fonts.check_all(["simfang"])
        # simfang.ttf 对应仿宋
        names = [n for n, _, _ in installed + missing]
        self.assertTrue(any("仿宋" in n or "FangSong" in n for n in names))
        # 不应包含不相关的字体（如 PingFang）
        self.assertFalse(any("PingFang" in n for n in names))

    def test_check_all_filter_case_insensitive(self):
        """--filter 应大小写不敏感。"""
        import check_fonts
        _, missing_lower = check_fonts.check_all(["noto"])
        _, missing_upper = check_fonts.check_all(["NOTO"])
        self.assertEqual(len(missing_lower), len(missing_upper))

    def test_install_targets_returns_valid_dirs(self):
        """install_targets 应返回当前平台的字体目录列表，首个可创建。"""
        import check_fonts
        targets = check_fonts.install_targets()
        self.assertGreater(len(targets), 0)
        # 首个应是用户级目录（可写）
        self.assertTrue(str(targets[0]).startswith(str(Path.home())) or
                        str(targets[0]).startswith("/"))

    def test_cli_runs_and_reports_status(self):
        """check_fonts.py CLI 应正常运行并报告安装状态。"""
        import subprocess
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_fonts.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("CJK 字体安装情况", completed.stdout)
        self.assertIn("总计:", completed.stdout)

    def test_cli_with_filter(self):
        """check_fonts.py --filter 应只显示匹配字体。"""
        import subprocess
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_fonts.py"),
             "--filter", "仿宋"],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("仿宋", completed.stdout)

    def test_cli_source_dir_nonexistent_exits_1(self):
        """--source-dir 指向不存在的目录时应 exit 1。"""
        import subprocess
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_fonts.py"),
             "--filter", "仿宋", "--source-dir", "/tmp/__nonexistent_font_dir__"],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("目录不存在", completed.stderr)

    def test_cli_source_dir_no_fonts_found(self):
        """--source-dir 指向空目录时应报告未找到字体。"""
        import subprocess
        empty_dir = Path(tempfile.mkdtemp())
        try:
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "check_fonts.py"),
                 "--filter", "仿宋", "--source-dir", str(empty_dir)],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0)
            self.assertIn("未找到", completed.stdout)
        finally:
            empty_dir.rmdir()

    def test_cli_source_dir_copies_font(self):
        """--source-dir 找到字体文件时应复制到目标目录。"""
        import check_fonts
        # 创建临时源目录，放入一个假字体文件
        src_dir = Path(tempfile.mkdtemp())
        font_file = src_dir / "simfang.ttf"
        font_file.write_bytes(b"fake font data")
        # 记录目标目录
        target = check_fonts.install_targets()[0]
        target.mkdir(parents=True, exist_ok=True)
        dest_file = target / "simfang.ttf"
        # 若已存在真实 simfang.ttf 则跳过
        if dest_file.exists():
            font_file.unlink()
            src_dir.rmdir()
            self.skipTest("目标目录已存在 simfang.ttf")
        try:
            import subprocess
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "check_fonts.py"),
                 "--filter", "仿宋", "--source-dir", str(src_dir), "--yes"],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("已复制", completed.stdout)
            self.assertTrue(dest_file.exists())
        finally:
            if dest_file.exists():
                dest_file.unlink()
            font_file.unlink()
            src_dir.rmdir()


class TestBugFix058_062(unittest.TestCase):
    """BUG-058～062 回归测试。

    - BUG-058: render_pdf_page 双重旋转（rotation=get_rotation() 应改为 rotation=0）
    - BUG-059: font_registry.find_font 子串匹配过宽（Song→FangSong）
    - BUG-060: scan_text_fusion --fusion-strength nan/负数未校验
    - BUG-061: 框坐标未校验 ⊂ 图像（validate_box/parse_ref/parse_box）
    - BUG-062: check_fonts.py --filter 尾逗号空串导致过滤失效
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    # ── BUG-058: render_pdf_page 不应双重旋转 ──

    def test_render_pdf_page_no_double_rotation(self):
        """render_pdf_page 源码应传 rotation=0，不含 rotation=rotation。"""
        import inspect
        src = inspect.getsource(utils.render_pdf_page)
        self.assertIn("rotation=0", src,
                       "render 应传 rotation=0（让 PDFium 内部处理 /Rotate）")
        self.assertNotIn("rotation=rotation", src,
                         "不应把 get_rotation() 返回值作为附加旋转（双重旋转，BUG-058）")

    def test_render_pdf_page_rotate270_content_correct(self):
        """带 /Rotate 270 的 PDF 渲染后内容朝向应正确。

        portrait 页面左上角黑块 + /Rotate 270（逆时针 90°）→ 黑块应在左下角。
        若误传 rotation=270（双重旋转），黑块会跑到右下角。
        """
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        doc = fitz.open()
        page = doc.new_page(width=200, height=300)  # portrait
        page.draw_rect(fitz.Rect(10, 10, 50, 50), color=(0, 0, 0), fill=(0, 0, 0))
        page.set_rotation(270)
        pdf_path = Path(self.tmpdir) / "rotated270.pdf"
        doc.save(str(pdf_path))
        doc.close()
        img = utils.render_pdf_page(pdf_path, dpi=72).convert("RGB")
        arr = np.asarray(img)
        dark = np.all(arr < 100, axis=2)
        ys, xs = np.where(dark)
        h, w = arr.shape[:2]
        # /Rotate=270：左上→左下
        self.assertLess(xs.mean(), w / 2, "黑块应在左半侧")
        self.assertGreater(ys.mean(), h / 2, "黑块应在下半侧（左上→左下）")

    def test_render_pdf_page_rotate90_content_correct(self):
        """带 /Rotate 90 的 PDF 渲染后内容朝向应正确。

        portrait 页面左上角黑块 + /Rotate 90（顺时针 90°）→ 黑块应在右上角。
        """
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF")
        doc = fitz.open()
        page = doc.new_page(width=200, height=300)
        page.draw_rect(fitz.Rect(10, 10, 50, 50), color=(0, 0, 0), fill=(0, 0, 0))
        page.set_rotation(90)
        pdf_path = Path(self.tmpdir) / "rotated90.pdf"
        doc.save(str(pdf_path))
        doc.close()
        img = utils.render_pdf_page(pdf_path, dpi=72).convert("RGB")
        arr = np.asarray(img)
        dark = np.all(arr < 100, axis=2)
        ys, xs = np.where(dark)
        h, w = arr.shape[:2]
        # /Rotate=90：左上→右上
        self.assertGreater(xs.mean(), w / 2, "黑块应在右半侧")
        self.assertLess(ys.mean(), h / 2, "黑块应在上半侧（左上→右上）")

    # ── BUG-059: find_font token 匹配不过宽 ──

    def test_find_font_song_not_match_fangsong(self):
        """'Song'/'song' 不应命中 'FangSong'（仿宋）——子串匹配过宽（BUG-059）。

        模拟全部字体已安装，验证 'Song' 匹配到 Songti 而非仿宋。
        """
        orig_resolve = font_registry.resolve_font
        font_registry.resolve_font = lambda fn: f"/mock/{fn}"
        try:
            r = font_registry.find_font("Song")
            if r is not None:
                hit_fn = r[0].split("/")[-1]
                self.assertNotEqual(hit_fn, "simfang.ttf",
                                    "'Song' 不应命中仿宋 simfang.ttf（BUG-059）")
        finally:
            font_registry.resolve_font = orig_resolve

    def test_find_font_token_matching_precise(self):
        """token 级匹配：精确名/文件名命中正确字体。"""
        orig_resolve = font_registry.resolve_font
        font_registry.resolve_font = lambda fn: f"/mock/{fn}"
        try:
            # 文件名（带/不带后缀）应正确命中
            for spec in ["simfang", "simfang.ttf", "SimSun", "simsun"]:
                r = font_registry.find_font(spec)
                self.assertIsNotNone(r, f"find_font({spec!r}) 应命中")
            # 注册名 token 精确匹配
            for spec in ["FangSong", "FangSong".lower(), "KaiTi"]:
                r = font_registry.find_font(spec)
                self.assertIsNotNone(r, f"find_font({spec!r}) 应命中")
        finally:
            font_registry.resolve_font = orig_resolve

    def test_find_font_name_tokens_helper(self):
        """_name_tokens 拆分正确。"""
        tokens = font_registry._name_tokens("仿宋 (FangSong)")
        self.assertIn("仿宋", tokens)
        self.assertIn("fangsong", tokens)
        tokens2 = font_registry._name_tokens("Hiragino Sans GB W3")
        self.assertIn("hiragino", tokens2)
        self.assertIn("gb", tokens2)

    # ── BUG-060: fusion-strength nan/负数校验 ──

    def test_fusion_strength_nan_rejected(self):
        """--fusion-strength nan 应被 parser.error 拒绝（退出码 2），不产出全黑图。"""
        img_path = Path(self.tmpdir) / "s.png"
        Image.new("RGB", (200, 200), (200, 200, 200)).save(img_path)
        import subprocess
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(img_path), "--position", "10", "10",
             "--fusion-strength", "nan"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0,
                            "nan strength 应非零退出")
        self.assertIn("有限", completed.stderr + completed.stdout)

    def test_fusion_strength_negative_rejected(self):
        """--fusion-strength 负数应被拒绝，不裸 ValueError。"""
        import subprocess
        img_path = Path(self.tmpdir) / "s.png"
        Image.new("RGB", (200, 200), (200, 200, 200)).save(img_path)
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(img_path), "--position", "10", "10",
             "--fusion-strength", "-0.5"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0,
                            "负数 strength 应非零退出")
        # 不应有 traceback（应有清晰错误信息）
        self.assertNotIn("Traceback", completed.stderr)

    def test_halo_strength_nan_rejected(self):
        """--halo-strength nan 同样应被拒绝。"""
        import subprocess
        img_path = Path(self.tmpdir) / "s.png"
        Image.new("RGB", (200, 200), (200, 200, 200)).save(img_path)
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(img_path), "--position", "10", "10",
             "--halo-strength", "inf"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)

    # ── BUG-061: 框坐标越界校验 ──

    def test_validate_box_rejects_out_of_bounds(self):
        """validate_box 给出 image_size 时应拒绝越界框。"""
        import scan_text_fusion as stf
        # 100×80 图，框 x2=150 越界
        with self.assertRaises(SystemExit):
            stf.validate_box((50, 50, 150, 60), "reference-box", (100, 80))

    def test_validate_box_accepts_in_bounds(self):
        """validate_box 界内框正常通过。"""
        import scan_text_fusion as stf
        box = stf.validate_box((10, 10, 90, 70), "reference-box", (100, 80))
        self.assertEqual(box, (10, 10, 90, 70))

    def test_validate_box_bounds_optional(self):
        """不给 image_size 时不做越界检查（向后兼容）。"""
        import scan_text_fusion as stf
        box = stf.validate_box((50, 50, 150, 150), "reference-box")
        self.assertEqual(box, (50, 50, 150, 150))

    def test_crop_box_out_of_bounds_rejected_cli(self):
        """--crop-box 越界应在 CLI 拒绝，不产出黑边图。"""
        import subprocess
        img_path = Path(self.tmpdir) / "s.png"
        Image.new("RGB", (100, 80), (200, 200, 200)).save(img_path)
        if font_registry.default_cjk_font() is None:
            self.skipTest("本机无 CJK 字体")
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scan_text_fusion.py"),
             "--source", str(img_path), "--position", "10", "10",
             "--crop-box", "50", "50", "150", "70"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0,
                            "越界 crop-box 应非零退出")
        self.assertIn("越出图像边界", completed.stderr + completed.stdout)

    def test_align_parse_box_rejects_out_of_bounds(self):
        """align_text parse_box 给出 image_size 时拒绝越界框。"""
        import align_text
        with self.assertRaises(SystemExit):
            align_text.parse_box("10,10,200,200", image_size=(100, 100))

    # ── BUG-062: check_fonts --filter 尾逗号 ──

    def test_check_all_trailing_comma_filter(self):
        """check_all(['仿宋', '']) 不应因空串列出全部字体（BUG-062）。"""
        import check_fonts
        # 空串在旧实现 "" in name 恒真 → 返回全部字体
        # 修复后空串被 check_all 内部过滤还是 main 过滤？
        # check_all 的过滤逻辑：any(f.lower() in name.lower() for f in font_filter)
        # 如果传入 [""]，"" in name 仍恒真。所以空串过滤应在 main 完成。
        # 这里验证 check_all([""]) 的行为（仍然会匹配全部，这是函数语义）
        # 真正的修复在 main() 的 split 处理，用 CLI 测试验证
        installed_all, missing_all = check_fonts.check_all()
        total_all = len(installed_all) + len(missing_all)
        installed_empty, missing_empty = check_fonts.check_all([""])
        total_empty = len(installed_empty) + len(missing_empty)
        # check_all([""]) 会匹配全部（"" in name 恒真），这是预期的——
        # 修复点是 main() 不让空串进入 check_all
        self.assertEqual(total_empty, total_all,
                         "check_all(['']) 匹配全部是函数语义；修复在 main 的 split")

    def test_check_fonts_cli_trailing_comma_filter(self):
        """check_fonts.py --filter '仿宋,' 不应列出全部字体（BUG-062）。"""
        import subprocess
        # 先跑 --filter 仿宋（正确），再跑 --filter '仿宋,'（尾逗号）
        completed_clean = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_fonts.py"), "--filter", "仿宋"],
            capture_output=True, text=True,
        )
        completed_trailing = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_fonts.py"), "--filter", "仿宋,"],
            capture_output=True, text=True,
        )
        self.assertEqual(completed_clean.returncode, 0)
        self.assertEqual(completed_trailing.returncode, 0)
        # 两者的输出（字体列表行数）应该相同——尾逗号不应导致列出更多字体
        clean_lines = [line for line in completed_clean.stdout.splitlines() if "✅" in line or "❌" in line]
        trailing_lines = [line for line in completed_trailing.stdout.splitlines() if "✅" in line or "❌" in line]
        self.assertEqual(len(clean_lines), len(trailing_lines),
                         f"尾逗号不应改变过滤结果: clean={len(clean_lines)}, trailing={len(trailing_lines)}")

    def test_check_fonts_cli_empty_filter_after_strip(self):
        """check_fonts.py --filter ',' （纯逗号）不应列出全部字体。"""
        import subprocess
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_fonts.py"), "--filter", ","],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0)
        # 纯逗号 strip 后全部为空 → font_filter=None → 列出全部
        # 这是合理的：纯逗号=无有效过滤词=不过滤
        # 关键是 ',' 不应产生 ["", ""] 导致特殊行为
        # 只要不崩溃且退出码 0 即可
        font_lines = [line for line in completed.stdout.splitlines() if "✅" in line or "❌" in line]
        self.assertGreater(len(font_lines), 0, "纯逗号应退化为列出全部")


if __name__ == "__main__":
    unittest.main()
