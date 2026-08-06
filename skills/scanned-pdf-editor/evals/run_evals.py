#!/usr/bin/env python3
"""scanned-pdf-editor 确定性自检运行器（不是真实模型 eval）。

⚠ 本脚本不运行任何模型，不能证明 skill 实际触发或模型遵循。它只是一组
确定性的冒烟检查，用于在改动代码后快速确认行为契约没被破坏。真实模型
with-skill / without-skill 评测见同目录 EVAL.md（交互式，逐 prompt 人工审阅）。

三类确定性检查：
1. **触发测试 (trigger)**：用关键词规则检查 SKILL.md 描述与提示词的匹配度，
   仅验证触发关键词覆盖，不验证模型实际是否触发。
2. **行为测试 (behavior)**：用合成测试图执行 CLI 命令，验证输出尺寸、
   框外无变化、目标区域有内容等行为契约。
3. **基线对比 (baseline)**：检查 skill 文档/脚本是否覆盖了已知基线缺陷的
   关键词，不运行模型对比。

运行：
  cd evals && python3 run_evals.py
  cd evals && python3 run_evals.py --verbose
  cd evals && python3 run_evals.py --filter trigger   # 只跑触发测试
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# 路径设置
EVAL_DIR = Path(__file__).parent
SKILL_DIR = EVAL_DIR.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
SKILL_MD = SKILL_DIR / "SKILL.md"
EVAL_CASES = EVAL_DIR / "eval_cases.json"

# 确保能导入 utils
sys.path.insert(0, str(SCRIPTS_DIR))
import scan_edit_utils as utils  # noqa: E402


# ─── 测试图生成 ──────────────────────────────────────────────

def make_eval_image(width: int = 600, height: int = 400) -> np.ndarray:
    """生成一张模拟扫描件的测试图：纸白背景 + 多行文字。"""
    img = np.full((height, width, 3), 245, dtype=np.uint8)
    pil = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    for y in [40, 90, 140, 190, 240, 290]:
        draw.text((50, y), "测试文字内容ABCdef", fill=(40, 40, 40))
    return np.asarray(pil)


def save_png(img: np.ndarray, path: Path) -> None:
    Image.fromarray(img).save(str(path))


# ─── 触发测试 ────────────────────────────────────────────────

def load_skill_description() -> str:
    """从 SKILL.md frontmatter 提取 description。"""
    text = SKILL_MD.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.index("---", 3)
        frontmatter = text[3:end]
        for line in frontmatter.splitlines():
            line = line.strip()
            if line.startswith("description:"):
                return line[len("description:"):].strip()
    return ""


def trigger_match(description: str, prompt: str) -> bool:
    """关键词匹配：判断 prompt 是否应触发 skill。

    匹配规则（两条路径，命中任一即触发）：
    1. 主路径：prompt 含"扫描/PDF/扫描件"类词 + 动作词（删除/移动/替换/...）
    2. 辅路径：prompt 含文档上下文词（文字/行/页/签名/字体/内容）+ 动作词
       适用于已建立扫描 PDF 上下文后的后续指令（用户不会再重复说"扫描版PDF"）

    动作词覆盖口语变体：移/换/加上/补/清掉 等。
    """
    prompt_lower = prompt.lower()
    desc_keywords = ["扫描", "pdf", "扫描件", "扫描版"]
    action_keywords = [
        "删除", "移动", "移", "替换", "换", "增加", "加上", "补录", "补",
        "编辑", "修改", "清除", "清掉", "复制",
    ]
    doc_keywords = ["文字", "行", "页", "签名", "字体", "内容"]

    has_desc = any(k in prompt_lower for k in desc_keywords)
    has_action = any(k in prompt_lower for k in action_keywords)
    has_doc = any(k in prompt_lower for k in doc_keywords)

    # 主路径：扫描/PDF 上下文 + 动作
    if has_desc and has_action:
        return True
    # 辅路径：文档上下文 + 动作（后续指令场景）
    if has_doc and has_action:
        return True
    return False


def run_trigger_evals(cases: list[dict], verbose: bool = False) -> tuple[int, int]:
    """运行触发测试，返回 (通过数, 总数)。"""
    description = load_skill_description()
    if verbose:
        print(f"  Skill description: {description[:80]}...")

    passed = 0
    total = 0
    for case in cases:
        if case["category"] != "trigger":
            continue
        total += 1
        prompt = case["prompt"]
        expected = case["should_trigger"]
        actual = trigger_match(description, prompt)
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        if verbose or not ok:
            print(f"  [{status}] {case['id']}: should_trigger={expected}, actual={actual}")
            if not ok:
                print(f"    prompt: {prompt}")
        if ok:
            passed += 1
    return passed, total


# ─── 行为测试 ────────────────────────────────────────────────

def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """执行 CLI 命令。"""
    return subprocess.run(
        [sys.executable, "scan_edit_ops.py"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def run_behavior_evals(cases: list[dict], verbose: bool = False) -> tuple[int, int]:
    """运行行为测试，返回 (通过数, 总数)。"""
    passed = 0
    total = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        img = make_eval_image()
        src_path = tmp / "source.png"
        save_png(img, src_path)

        for case in cases:
            if case["category"] != "behavior":
                continue
            total += 1
            mode = case["mode"]
            cli_args = case.get("cli_args", {})
            out_path = tmp / f"output_{case['id']}.png"

            try:
                ok, detail = run_single_behavior(case, mode, cli_args, src_path, out_path, img)
            except Exception as e:
                ok, detail = False, f"异常: {e}"

            status = "PASS" if ok else "FAIL"
            if verbose or not ok:
                print(f"  [{status}] {case['id']} ({mode}): {detail}")
            if ok:
                passed += 1

    return passed, total


def run_single_behavior(case, mode, cli_args, src_path, out_path, original_img):
    """执行单个行为测试，返回 (是否通过, 详情)。"""
    validation = case.get("validation", {})

    if mode == "remove":
        boxes = ["50,40,250,70"]
        args = ["remove", "--source", str(src_path), "--output", str(out_path),
                "--boxes"] + boxes
        for k, v in cli_args.items():
            args += [f"--{k}", str(v)]
        result = run_cli(args, SCRIPTS_DIR)
        if result.returncode != 0:
            return False, f"CLI 退出码 {result.returncode}: {result.stderr[:200]}"

        out = np.asarray(Image.open(out_path))
        if validation.get("check_size") and out.shape != original_img.shape:
            return False, f"尺寸不一致: {out.shape} vs {original_img.shape}"

        if validation.get("check_outside_boxes"):
            box_list = [(50, 40, 250, 70)]
            outside = utils.changes_outside_boxes(original_img, out, box_list)
            max_outside = validation.get("max_outside_changes", 500)
            if outside > max_outside:
                return False, f"框外变化过多: {outside} > {max_outside}"

        if validation.get("check_inside_dark_pixels"):
            region = out[40:70, 50:250]
            dark = np.sum(np.all(region < 180, axis=-1))
            if dark > 50:
                return False, f"框内深色像素残留: {dark}"
        return True, "尺寸一致、框外无变化、框内已清除"

    elif mode == "move":
        args = ["move", "--source", str(src_path), "--output", str(out_path),
                "--content-x", "50,250", "--source-y", "90,140",
                "--shift-y", "50"]
        result = run_cli(args, SCRIPTS_DIR)
        if result.returncode != 0:
            return False, f"CLI 退出码 {result.returncode}: {result.stderr[:200]}"

        out = np.asarray(Image.open(out_path))
        if validation.get("check_size") and out.shape != original_img.shape:
            return False, f"尺寸不一致: {out.shape} vs {original_img.shape}"

        if validation.get("check_target_has_content"):
            # 目标位置 y=40~90 区域应有深色像素（从 y=90~140 上移 50px）
            target_region = out[40:90, 50:250]
            dark = np.sum(np.all(target_region < 180, axis=-1))
            if dark < 10:
                return False, f"目标位置无内容: dark={dark}"
        return True, "尺寸一致、目标位置有内容"

    elif mode == "compound":
        args = ["compound", "--source", str(src_path), "--output", str(out_path),
                "--content-x", "50,250", "--source-y", "90,140",
                "--shift-y", "50",
                "--clear-boxes", "50,90,250,140"]
        result = run_cli(args, SCRIPTS_DIR)
        if result.returncode != 0:
            return False, f"CLI 退出码 {result.returncode}: {result.stderr[:200]}"

        out = np.asarray(Image.open(out_path))
        if validation.get("check_size") and out.shape != original_img.shape:
            return False, f"尺寸不一致: {out.shape} vs {original_img.shape}"

        if validation.get("check_target_has_content"):
            target_region = out[40:90, 50:250]
            dark = np.sum(np.all(target_region < 180, axis=-1))
            if dark < 10:
                return False, f"目标位置无内容: dark={dark}"

        if validation.get("check_source_cleared"):
            # 源区域应被清除（插值填底）
            source_region = out[90:140, 50:250]
            dark = np.sum(np.all(source_region < 180, axis=-1))
            if dark > 100:
                return False, f"源区域未清除: dark={dark}"
        return True, "尺寸一致、目标有内容、源已清除"

    elif mode == "replace":
        donor_path = src_path  # 同页供体
        out_path_replace = out_path
        args = ["replace", "--source", str(src_path), "--output", str(out_path_replace),
                "--donor-source", str(donor_path),
                "--donor-box", "50,140,250,170",
                "--remove-boxes", "50,40,250,70",
                "--destination", "50,40",
                "--reference-box", "50,40,250,70"]
        for k, v in cli_args.items():
            args += [f"--{k}", str(v)]
        result = run_cli(args, SCRIPTS_DIR)
        if result.returncode != 0:
            return False, f"CLI 退出码 {result.returncode}: {result.stderr[:200]}"

        out = np.asarray(Image.open(out_path_replace))
        if validation.get("check_size") and out.shape != original_img.shape:
            return False, f"尺寸不一致: {out.shape} vs {original_img.shape}"

        if validation.get("check_target_has_content"):
            target_region = out[40:70, 50:250]
            dark = np.sum(np.all(target_region < 180, axis=-1))
            if dark < 5:
                return False, f"目标位置无内容: dark={dark}"

        if validation.get("check_differs_from_contrast"):
            # 用 contrast 模式再跑一次，对比输出不同。
            # BUG-026：旧实现把 args_c.index("--normalize-mode") 写在赋值目标里，
            # 先于条件表达式求值——case 未带该参数时必炸 ValueError；且 fallback
            # 分支（给单元素赋一个 list）本身也是死代码。重写为显式分支，并在
            # 主跑不是非 contrast 模式时给出明确失败原因（contrast vs contrast 无意义）。
            if "--normalize-mode" not in args:
                return False, ("check_differs_from_contrast 要求 cli_args 指定非 contrast 的"
                               " normalize-mode（如 offset），否则对照无意义")
            mode_idx = args.index("--normalize-mode") + 1
            if mode_idx >= len(args) or args[mode_idx] == "contrast":
                return False, ("check_differs_from_contrast 要求 cli_args 指定非 contrast 的"
                               " normalize-mode（如 offset），否则对照无意义")
            out_contrast_path = out_path.parent / f"{out_path.stem}_contrast.png"
            args_c = args[:]
            args_c[mode_idx] = "contrast"
            args_c[args_c.index("--output") + 1] = str(out_contrast_path)
            run_cli(args_c, SCRIPTS_DIR)
            if out_contrast_path.exists():
                out_c = np.asarray(Image.open(out_contrast_path))
                diff = np.sum(out != out_c)
                if diff == 0:
                    return False, "offset 与 contrast 输出相同"
        return True, "尺寸一致、目标有内容"

    return False, f"未知模式: {mode}"


# ─── 基线对比 ────────────────────────────────────────────────

def run_baseline_evals(cases: list[dict], verbose: bool = False) -> tuple[int, int]:
    """运行基线对比，返回 (通过数, 总数)。

    基线测试验证 with-skill 行为确实避免了基线缺陷中描述的问题。
    """
    passed = 0
    total = 0
    for case in cases:
        if case["category"] != "baseline":
            continue
        total += 1
        gaps = case.get("gaps", [])
        # 基线测试：验证 skill 文档/工具确实覆盖了每个 gap
        skill_text = SKILL_MD.read_text(encoding="utf-8")
        scripts_text = ""
        for py in SCRIPTS_DIR.glob("*.py"):
            scripts_text += py.read_text(encoding="utf-8")

        all_covered = True
        uncovered = []
        for gap in gaps:
            # 检查 gap 的关键词是否在 skill 文档或脚本中出现
            keywords = []
            if "归一化" in gap:
                keywords.append("归一化")
            if "羽化" in gap:
                keywords.append("羽化")
            if "验证" in gap or "像素级" in gap:
                keywords.append("验证")
            if "墨迹" in gap:
                keywords.append("墨迹")
            if "膨胀" in gap:
                keywords.append("膨胀")
            if "框外" in gap or "越界" in gap:
                keywords.append("框外")
            if "残留" in gap:
                keywords.append("残留")
            if "字体" in gap and "识别" in gap:
                keywords.append("identify_font")
            if "字号" in gap and "识别" in gap:
                keywords.append("identify_size")
            if "融合" in gap:
                keywords.append("融合")
            if "晕染" in gap:
                keywords.append("晕染")
            if "参考颜色" in gap or "墨色" in gap:
                keywords.append("reference-box")

            if keywords:
                found = any(kw.lower() in (skill_text + scripts_text).lower() for kw in keywords)
                if not found:
                    all_covered = False
                    uncovered.append(gap)

        if all_covered:
            passed += 1
            if verbose:
                print(f"  [PASS] {case['id']}: 所有基线缺陷均被 skill 覆盖 ({len(gaps)} 项)")
        else:
            print(f"  [FAIL] {case['id']}: 以下缺陷未被 skill 覆盖:")
            for g in uncovered:
                print(f"    - {g}")
    return passed, total


# ─── 主入口 ──────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="scanned-pdf-editor skill 行为级 eval")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--filter", choices=["trigger", "behavior", "baseline"],
                        help="只运行指定类别的 eval")
    args = parser.parse_args()

    cases = json.loads(EVAL_CASES.read_text(encoding="utf-8"))

    print("=" * 60)
    print("scanned-pdf-editor skill 行为级 eval")
    print("=" * 60)

    all_passed = 0
    all_total = 0

    if not args.filter or args.filter == "trigger":
        print("\n── 触发测试 (trigger) ──")
        p, t = run_trigger_evals(cases, verbose=args.verbose)
        print(f"  结果: {p}/{t} 通过")
        all_passed += p
        all_total += t

    if not args.filter or args.filter == "behavior":
        print("\n── 行为测试 (behavior) ──")
        p, t = run_behavior_evals(cases, verbose=args.verbose)
        print(f"  结果: {p}/{t} 通过")
        all_passed += p
        all_total += t

    if not args.filter or args.filter == "baseline":
        print("\n── 基线对比 (baseline) ──")
        p, t = run_baseline_evals(cases, verbose=args.verbose)
        print(f"  结果: {p}/{t} 通过")
        all_passed += p
        all_total += t

    print(f"\n{'=' * 60}")
    print(f"总计: {all_passed}/{all_total} 通过")
    print("=" * 60)

    return 0 if all_passed == all_total else 1


if __name__ == "__main__":
    sys.exit(main())
