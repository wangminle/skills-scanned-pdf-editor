"""跨平台 CJK 字体注册表。

统一 identify_font.py / scan_text_fusion.py / 测试的字体查找逻辑，避免把任一脚本的
默认字体硬编码到某个平台的路径（曾导致 Windows 上默认找 macOS Hiragino、自测全挂）。

设计：维护一份"名称 -> (文件名, ttc 索引)"的跨平台候选表，在一份跨平台字体目录列表里
按文件名查找；找不到的自动跳过。调用方拿到的是本机真实存在的字体路径。
"""
from __future__ import annotations

import os
import sys

# 跨平台字体目录（按优先级）；找不到的目录自然跳过。
# macOS 注意：双击字体文件"为我安装"会落到 ~/Library/Fonts（用户级），
# 此前 FONT_DIRS 未收录该目录，导致"安装 simfang.ttf 后重跑"在 macOS 上仍找不到字体，
# add 路线无法复现（复现对比报告 task002add / 字体 bug）。现一并收录用户级与网络共享目录。
FONT_DIRS = [
    r"C:\Windows\Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),  # macOS 用户级（双击安装的默认落点）
    "/Network/Library/Fonts",                # macOS 网络共享字体
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
]

# 名称 -> (文件名, ttc 索引)。覆盖 Windows / macOS / Linux 常见 CJK 字体。
CJK_FONTS: dict[str, tuple[str, int]] = {
    # Windows
    "仿宋 (FangSong)":    ("simfang.ttf", 0),
    "宋体 (SimSun)":       ("simsun.ttc", 0),
    "黑体 (SimHei)":       ("simhei.ttf", 0),
    "楷体 (KaiTi)":        ("simkai.ttf", 0),
    "等线 (DengXian)":     ("Deng.ttf", 0),
    "微软雅黑 (MSYH)":     ("msyh.ttc", 0),
    # macOS
    "STSong (华文宋体)":   ("STSong.ttf", 0),
    "Songti SC":           ("Songti.ttc", 0),
    "PingFang SC":         ("PingFang.ttc", 0),
    "Hiragino Sans GB W3": ("Hiragino Sans GB.ttc", 0),
    "Hiragino Sans GB W6": ("Hiragino Sans GB.ttc", 2),
    # Linux / 通用
    "Noto Serif CJK SC":   ("NotoSerifCJKsc.ttc", 0),
    "Noto Sans CJK SC":    ("NotoSansCJKsc.ttc", 0),
    "Source Han Serif SC": ("SourceHanSerifSC.otf", 0),
    "Source Han Sans SC":  ("SourceHanSansSC.otf", 0),
    "WenQuanYi Zen Hei":   ("wqy-zenhei.ttc", 0),
}

# default_cjk_font() 的优先级：正文优先衬线（仿宋/宋体），与中文公文/法律文书惯例一致。
_PREFERRED_KEYWORDS = [
    "仿宋", "宋体", "STSong", "Noto Serif", "Source Han Serif", "Songti",
    "Hiragino", "楷体", "PingFang",
    "黑体", "等线", "雅黑", "Noto Sans", "Source Han Sans", "WenQuanYi",
]


def resolve_font(filename: str) -> str | None:
    """按文件名在 FONT_DIRS 里查找，返回首个存在的完整路径；找不到返回 None。"""
    if not filename:
        return None
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    for d in FONT_DIRS:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None


def available_cjk_fonts() -> list[tuple[str, str, int]]:
    """返回本机已安装的 CJK 字体 [(名称, 路径, ttc 索引)]，按注册表顺序。"""
    out = []
    for name, (fn, idx) in CJK_FONTS.items():
        p = resolve_font(fn)
        if p:
            out.append((name, p, idx))
    return out


def _name_tokens(name: str) -> list[str]:
    """把注册名拆成语义 token，用于精确/前缀匹配。

    拆分规则：去掉括号后，按空格/标点分词，再补充括号内的整体英文段。
    例如 '仿宋 (FangSong)' → ['仿宋', 'fangsong']，
         'Songti SC' → ['songti', 'sc']，
         'Hiragino Sans GB W3' → ['hiragino', 'sans', 'gb', 'w3']。
    """
    import re
    # 先提取括号内的英文段（如 FangSong、SimSun），作为整体 token
    paren_match = re.search(r"\(([^\)]+)\)", name)
    tokens = []
    # 括号前的主体（中文部分或英文短语）
    main = re.split(r"[\(\)]", name)[0].strip()
    for part in re.split(r"[\s\-_,]+", main):
        if part:
            tokens.append(part.lower())
    if paren_match:
        inner = paren_match.group(1).strip()
        if inner:
            tokens.append(inner.lower())
    return tokens


def find_font(spec: str | None) -> tuple[str, int] | None:
    """把用户给的 --font 解析成 (路径, 索引)。

    支持三种写法：完整路径、注册名（如 '仿宋'/'宋体'，token 匹配）、纯文件名。
    找不到返回 None。

    匹配规则（BUG-059）：旧实现用 ``spec in name`` 裸子串匹配，过宽——
    'Song' 会命中 'FangSong'（仿宋），'SC' 命中 'Songti SC'，'GB' 命中
    'Hiragino Sans GB'。改为 token 级匹配：注册名拆成语义段（仿宋/FangSong/
    Songti/SC），用户输入须**精确等于**某 token 或是其前缀，而非任意子串。
    中文同理：'宋' 不应命中 '仿宋'（'宋' 只是 token '仿宋' 的后缀，不是前缀）。
    """
    if not spec:
        return None
    if os.path.exists(spec):
        return (spec, 0)
    spec_l = spec.lower()
    for name, (fn, idx) in CJK_FONTS.items():
        matched = False
        # 文件名精确匹配（允许不带后缀，如 'simfang' 匹配 'simfang.ttf'）
        fn_lower = fn.lower()
        fn_stem = fn_lower.rsplit(".", 1)[0] if "." in fn_lower else fn_lower
        if spec_l == fn_lower or spec_l == fn_stem:
            matched = True
        # token 匹配：用户输入须精确等于某 token 或是其前缀（≥2 字符）
        # 中文也走此路径：'宋' 不是 '仿宋' 的前缀（是后缀），不会误命中
        if not matched:
            for token in _name_tokens(name):
                if spec_l == token or (len(spec_l) >= 2 and token.startswith(spec_l)):
                    matched = True
                    break
        if matched:
            p = resolve_font(fn)
            if p:
                return (p, idx)
    p = resolve_font(spec)
    if p:
        return (p, 0)
    return None


def default_cjk_font() -> tuple[str, int] | None:
    """返回本机首个可用 CJK 字体 (路径, 索引)，供默认值/测试用；无则 None。

    按正文优先级选（仿宋 > 宋体 > ...），保证"默认"是个合理字体而不是某个平台的残留。
    """
    avail = available_cjk_fonts()
    if not avail:
        return None
    for kw in _PREFERRED_KEYWORDS:
        for name, p, idx in avail:
            if kw in name:
                return (p, idx)
    return (avail[0][1], avail[0][2])


def require_default_font() -> tuple[str, int]:
    """同 default_cjk_font，但找不到时报清晰错误并退出（给 CLI 默认值用）。"""
    res = default_cjk_font()
    if res is None:
        print(
            "错误: 本机未找到任何内置 CJK 字体。请先用 identify_font.py 识别原文字体，\n"
            "      再用 --font 指定其路径（或把字体文件放到系统字体目录）。",
            file=sys.stderr,
        )
        sys.exit(2)
    return res
