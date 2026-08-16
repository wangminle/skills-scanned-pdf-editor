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
    # Songti.ttc 内含多字重（0=Black/1=Bold/3=Light/4=STSong/6=Regular）。
    # 「Songti SC」裸名按惯例指 Regular（旧映射 index 0 实为 Black，细笔画文书
    # 识别曾被误导）；Light/Regular 单列，供细笔画原文（仿宋系）交叉验证。
    "Songti SC":           ("Songti.ttc", 6),
    "Songti SC Light":     ("Songti.ttc", 3),
    "Songti SC Regular":   ("Songti.ttc", 6),
    "STHeiti Light":       ("STHeiti Light.ttc", 0),
    "STHeiti Medium":      ("STHeiti Medium.ttc", 0),
    "PingFang SC":         ("PingFang.ttc", 0),
    "Hiragino Sans GB W3": ("Hiragino Sans GB.ttc", 0),
    "Hiragino Sans GB W6": ("Hiragino Sans GB.ttc", 2),
    # Linux / 通用
    "Noto Serif CJK SC":   ("NotoSerifCJKsc.ttc", 0),
    "Noto Sans CJK SC":    ("NotoSansCJKsc.ttc", 0),
    # Google Fonts 独立发行名（与 CJK 合集 ttc 并存，皆常见）
    "Noto Sans SC":        ("NotoSansSC.ttf", 0),
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

    支持三种写法：完整路径、注册名（如 '仿宋'/'宋体'/'Hiragino Sans GB W6'）、纯文件名。
    找不到返回 None。

    匹配优先级（BUG-063 / BUG-059）：
    1. 完整注册名精确匹配（大小写不敏感）——identify_font 输出可直接回填；
    2. 多词 token 全集匹配——查询词全部出现在注册名 token 中，取覆盖最完整者
       （区分 W3/W6，避免共享前缀误命中）；
    3. 文件名精确/词干匹配；
    4. 单词 token 精确或前缀匹配（≥2 字符）。旧实现用 ``spec in name`` 裸子串
       过宽（'Song'→仿宋），故单词路径仍禁止任意子串。
    """
    if not spec:
        return None
    if os.path.exists(spec):
        return (spec, 0)
    spec_l = spec.lower().strip()
    if not spec_l:
        return None

    # 1) 完整注册名精确匹配（identify_font 「=> 最优: …」可直接回填）
    for name, (fn, idx) in CJK_FONTS.items():
        if spec_l == name.lower():
            p = resolve_font(fn)
            if p:
                return (p, idx)

    # 2) 多词查询：要求查询侧每个 token 都能在注册名 token 中精确命中
    query_tokens = [t for t in _name_tokens(spec_l) if t]
    # 对无括号的纯查询串，_name_tokens 仍按空格拆分
    if not query_tokens:
        query_tokens = [t for t in spec_l.replace(",", " ").split() if t]
    if len(query_tokens) >= 2:
        best: tuple[str, int] | None = None
        best_score = -1
        for name, (fn, idx) in CJK_FONTS.items():
            name_tokens = _name_tokens(name)
            if not name_tokens:
                continue
            if not all(qt in name_tokens for qt in query_tokens):
                continue
            # 覆盖分：查询 token 全中 + 注册名越短（更具体）越好
            score = len(query_tokens) * 100 - len(name_tokens)
            if score > best_score:
                p = resolve_font(fn)
                if p:
                    best = (p, idx)
                    best_score = score
        if best is not None:
            return best

    # 3) 文件名 / 4) 单词 token
    for name, (fn, idx) in CJK_FONTS.items():
        matched = False
        fn_lower = fn.lower()
        fn_stem = fn_lower.rsplit(".", 1)[0] if "." in fn_lower else fn_lower
        if spec_l == fn_lower or spec_l == fn_stem:
            matched = True
        if not matched and len(query_tokens) == 1:
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
