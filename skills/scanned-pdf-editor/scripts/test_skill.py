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
sys.path.insert(0, str(Path(__file__).parent))

import scan_edit_utils as utils
import font_registry


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
            [sys.executable, str(Path(__file__).parent / "identify_size.py"),
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
        """两张高覆盖、比例接近的图，strict 模式应报错而非静默替换。"""
        try:
            import fitz
        except ImportError:
            self.skipTest("未安装 PyMuPDF，跳过多图测试")
        full = self._save_png("full.png", np.full((100, 100, 3), 200, dtype=np.uint8))
        original = self._make_pdf_with_images(
            "ambig.pdf",
            [((0, 0, 90, 90), full), ((0, 0, 85, 85), full)],
        )
        doc = fitz.open(str(original))
        page = doc[0]
        images = page.get_images(full=True)
        doc.close()
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
            [sys.executable, str(Path(__file__).parent / "verify_outputs.py"), "--config", str(cfg)],
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
            [sys.executable, str(Path(__file__).parent / "verify_outputs.py"), "--config", str(cfg)],
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

    # ── BUG-018：evals.json 应为合法 JSON ──

    def test_evals_json_is_valid(self):
        """evals/evals.json 必须是可解析的合法 JSON。"""
        import json
        evals_path = Path(__file__).parent.parent / "evals" / "evals.json"
        if not evals_path.exists():
            self.skipTest("evals/evals.json 不存在")
        data = json.loads(evals_path.read_text(encoding="utf-8"))
        self.assertEqual(data["skill_name"], "scanned-pdf-editor")
        self.assertGreaterEqual(len(data["evals"]), 1)
        for ev in data["evals"]:
            self.assertIn("id", ev)
            self.assertIn("prompt", ev)
            self.assertIn("expectations", ev)


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


if __name__ == "__main__":
    unittest.main()
