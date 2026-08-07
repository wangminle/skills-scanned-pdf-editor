#!/usr/bin/env python3
"""检查本机 CJK 字体安装情况，提供安装引导。

扫描 font_registry.CJK_FONTS 中注册的全部字体，报告已安装 / 未安装状态。
对未安装的字体，给出平台特定的安装方法；支持从用户指定目录（如挂载的
Windows 分区、U盘）自动复制字体文件到本机字体目录。

用法:
  # 查看安装状态（只读，不做任何修改）
  python3 scripts/check_fonts.py

  # 从指定目录查找并复制缺失字体（如挂载的 Windows C:\\Windows\\Fonts）
  python3 scripts/check_fonts.py --source-dir /Volumes/Windows/Windows/Fonts

  # 只检查特定字体
  python3 scripts/check_fonts.py --filter 仿宋,宋体

  # 复制时跳过确认提示（批处理场景）
  python3 scripts/check_fonts.py --source-dir /path/to/fonts --yes
"""
import argparse
import platform
import shutil
import sys
from pathlib import Path

import font_registry

# ── 字体来源信息 ──
# Windows 系统字体为微软专有，随 Windows 附带。合法使用前提：你拥有一份
# Windows 许可（绝大多数用户通过预装或零售获得）。从自己的 Windows 机器/
# 分区复制到 macOS/Linux 用于本工具是合理的使用方式。
# 以下信息仅做来源指引，不提供下载链接，也不鼓励从第三方未授权渠道获取。
FONT_SOURCES: dict[str, str] = {
    "simfang.ttf": "Windows 系统自带（C:\\Windows\\Fonts\\simfang.ttf）。公文/法律文书正文标准字体（GB/T 9704）。",
    "simsun.ttc": "Windows 系统自带（C:\\Windows\\Fonts\\simsun.ttc）。",
    "simhei.ttf": "Windows 系统自带（C:\\Windows\\Fonts\\simhei.ttf）。",
    "simkai.ttf": "Windows 系统自带（C:\\Windows\\Fonts\\simkai.ttf）。",
    "Deng.ttf": "Windows 10+ 系统自带（C:\\Windows\\Fonts\\Deng.ttf）。",
    "msyh.ttc": "Windows Vista+ 系统自带（C:\\Windows\\Fonts\\msyh.ttc）。",
    "STSong.ttf": "macOS 系统自带（/System/Library/Fonts/STSong.ttf）。",
    "Songti.ttc": "macOS 系统自带（/System/Library/Fonts/Supplemental/Songti.ttc）。",
    "PingFang.ttc": "macOS 10.11+ 系统自带。",
    "Hiragino Sans GB.ttc": "macOS 系统自带。",
    "NotoSerifCJKsc.ttc": "开源字体，Google Noto 项目。brew install --cask font-noto-serif-cjk-sc 或从 fonts.google.com 下载。",
    "NotoSansCJKsc.ttc": "开源字体，Google Noto 项目。brew install --cask font-noto-sans-cjk-sc 或从 fonts.google.com 下载。",
    "SourceHanSerifSC.otf": "开源字体，Adobe Source Han 系列。brew install --cask font-source-han-serif-sc 或从 github.com/adobe-fonts 下载。",
    "SourceHanSansSC.otf": "开源字体，Adobe Source Han 系列。brew install --cask font-source-han-sans-sc 或从 github.com/adobe-fonts 下载。",
    "wqy-zenhei.ttc": "开源字体，文泉驿正黑。Linux: apt install fonts-wqy-zenhei。",
}

# 各平台字体安装目标目录（按优先级）
def install_targets() -> list[Path]:
    """返回当前平台的字体安装目标目录列表（可写的优先）。"""
    system = platform.system()
    if system == "Darwin":  # macOS
        return [
            Path.home() / "Library" / "Fonts",       # 用户级（推荐）
            Path("/Library/Fonts"),                    # 系统级（需 sudo）
        ]
    elif system == "Windows":
        return [Path("C:/Windows/Fonts")]
    else:  # Linux
        return [
            Path.home() / ".local" / "share" / "fonts",
            Path.home() / ".fonts",
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
        ]


def check_all(font_filter: list[str] | None = None) -> tuple[list[tuple[str, str, int]], list[tuple[str, str, int]]]:
    """返回 (已安装, 未安装) 列表，每项为 (名称, 文件名, ttc索引)。"""
    installed = []
    missing = []
    for name, (fn, idx) in font_registry.CJK_FONTS.items():
        if font_filter:
            if not any(f.lower() in name.lower() or f.lower() in fn.lower() for f in font_filter):
                continue
        path = font_registry.resolve_font(fn)
        if path:
            installed.append((name, fn, idx))
        else:
            missing.append((name, fn, idx))
    return installed, missing


def print_status(installed: list, missing: list) -> None:
    """打印字体安装状态总览。"""
    print("CJK 字体安装情况")
    print("=" * 60)
    print()

    if installed:
        print(f"已安装 ({len(installed)}):")
        for name, fn, _ in installed:
            print(f"  ✅ {name:<26} ({fn})")
        print()

    if missing:
        print(f"未安装 ({len(missing)}):")
        for name, fn, _ in missing:
            source = FONT_SOURCES.get(fn, "来源未知")
            # 截取来源描述的第一句
            short = source.split("。")[0] + "。" if "。" in source else source
            print(f"  ❌ {name:<26} ({fn})")
            print(f"      来源: {short}")
        print()

    total = len(installed) + len(missing)
    print(f"总计: {len(installed)}/{total} 已安装")
    if missing:
        print(f"缺失 {len(missing)} 个字体。")
    else:
        print("全部字体已安装。")


def print_install_guide(missing: list) -> None:
    """对缺失字体打印平台特定的安装指引。"""
    if not missing:
        return

    system = platform.system()
    targets = install_targets()
    target = targets[0]  # 推荐目录

    print()
    print("安装方法")
    print("-" * 60)

    # 按来源类型分组
    windows_fonts = [(n, fn) for n, fn, _ in missing
                     if fn in ("simfang.ttf", "simsun.ttc", "simhei.ttf",
                               "simkai.ttf", "Deng.ttf", "msyh.ttc")]
    opensource_fonts = [(n, fn) for n, fn, _ in missing
                        if fn in ("NotoSerifCJKsc.ttc", "NotoSansCJKsc.ttc",
                                  "SourceHanSerifSC.otf", "SourceHanSansSC.otf",
                                  "wqy-zenhei.ttc")]
    other_fonts = [(n, fn) for n, fn, _ in missing
                   if (n, fn) not in windows_fonts and (n, fn) not in opensource_fonts]

    if windows_fonts:
        print()
        print("▸ Windows 系统字体（微软专有，需自行从 Windows 获取）:")
        for name, fn in windows_fonts:
            print(f"  {name} ({fn}):")
            print(f"    {FONT_SOURCES.get(fn, '')}")
        print()
        if system == "Darwin":
            print("  macOS 安装步骤:")
            print("    1. 从你的 Windows 机器复制字体文件（如 simfang.ttf）")
            print("    2. 双击字体文件 -> 点击「安装字体」（自动落到 ~/Library/Fonts/）")
            print(f"       或手动复制到: {target}/")
            print("    3. 重新运行本脚本验证: python3 scripts/check_fonts.py")
            print("    4. 重跑字体识别: python3 scripts/identify_font.py --source page.png ...")
        elif system == "Windows":
            print("  Windows: 这些字体应已随系统安装。若缺失，从 Windows 安装介质恢复。")
        else:
            print("  Linux 安装步骤:")
            print("    1. 从你的 Windows 机器复制字体文件")
            print(f"    2. 复制到: {target}/")
            print("    3. 刷新字体缓存: fc-cache -fv")
            print("    4. 重新运行本脚本验证")

    if opensource_fonts:
        print()
        print("▸ 开源字体（免费，可合法下载）:")
        for name, fn in opensource_fonts:
            print(f"  {name} ({fn}):")
            print(f"    {FONT_SOURCES.get(fn, '')}")
        print()
        if system == "Darwin":
            print("  macOS 安装（Homebrew）:")
            for name, fn in opensource_fonts:
                if "Noto" in fn:
                    pkg = "font-noto-serif-cjk-sc" if "Serif" in fn else "font-noto-sans-cjk-sc"
                elif "SourceHan" in fn:
                    pkg = "font-source-han-serif-sc" if "Serif" in fn else "font-source-han-sans-sc"
                else:
                    pkg = None
                if pkg:
                    print(f"    brew install --cask {pkg}")
            print(f"  或手动下载后双击安装（落到 {target}/）")
        elif system == "Linux":
            print("  Linux 安装:")
            for name, fn in opensource_fonts:
                if "wqy" in fn:
                    print(f"    apt install fonts-wqy-zenhei  # {name}")
                elif "Noto" in fn:
                    print(f"    apt install fonts-noto-cjk  # {name}")
            print(f"  或下载后复制到 {target}/ 并 fc-cache -fv")

    if other_fonts:
        print()
        print("▸ 其他字体:")
        for name, fn in other_fonts:
            print(f"  {name} ({fn}):")
            print(f"    {FONT_SOURCES.get(fn, '请查阅字体来源说明。')}")

    print()
    print("提示: 安装字体后无需重启，直接重跑 identify_font.py 即可生效。")
    print(f"本工具搜索的字体目录: {', '.join(str(d) for d in font_registry.FONT_DIRS)}")


def scan_and_copy(source_dir: Path, missing: list, yes: bool) -> None:
    """在 source_dir 中查找缺失字体文件，找到则复制到目标目录。"""
    if not source_dir.exists():
        print(f"错误: 目录不存在: {source_dir}", file=sys.stderr)
        sys.exit(1)
    if not source_dir.is_dir():
        print(f"错误: 不是目录: {source_dir}", file=sys.stderr)
        sys.exit(1)

    missing_fns = {fn.lower() for _, fn, _ in missing}
    found = []
    for f in source_dir.rglob("*"):
        if f.is_file() and f.name.lower() in missing_fns:
            found.append(f)

    if not found:
        print(f"在 {source_dir} 中未找到任何缺失字体文件。")
        print(f"缺失字体文件名: {', '.join(fn for _, fn, _ in missing)}")
        print("提示: Windows 字体通常在 C:\\Windows\\Fonts\\ 目录下。")
        print("      挂载 Windows 分区后，路径类似 /Volumes/Windows/Windows/Fonts/")
        return

    targets = install_targets()
    target = targets[0]
    target.mkdir(parents=True, exist_ok=True)

    print(f"在 {source_dir} 中找到 {len(found)} 个缺失字体:")
    for f in found:
        print(f"  {f.name}  ->  {target / f.name}")

    if not yes:
        print()
        resp = input("是否复制以上字体到目标目录？[y/N] ").strip().lower()
        if resp != "y":
            print("已取消。")
            return

    copied = []
    for f in found:
        dest = target / f.name
        if dest.exists():
            print(f"  跳过 {f.name}（目标已存在）")
            continue
        shutil.copy2(f, dest)
        copied.append(f.name)
        print(f"  已复制 {f.name}")

    if copied:
        print()
        print(f"成功复制 {len(copied)} 个字体到 {target}")
        print("请重跑本脚本验证安装结果。")
    else:
        print("没有新复制任何字体（目标已存在或取消）。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="检查 CJK 字体安装情况并提供安装引导。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python3 scripts/check_fonts.py\n"
            "  python3 scripts/check_fonts.py --filter 仿宋\n"
            "  python3 scripts/check_fonts.py --source-dir /Volumes/Windows/Windows/Fonts\n"
        ),
    )
    parser.add_argument(
        "--filter", default=None,
        help="只检查匹配的字体（逗号分隔，如 仿宋,宋体）",
    )
    parser.add_argument(
        "--source-dir", default=None, type=Path,
        help="从指定目录查找缺失字体并复制到本机字体目录",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="复制时跳过确认提示",
    )
    args = parser.parse_args()

    # BUG-062：args.filter.split(",") 对尾逗号（如 "仿宋,"）产生空串 "",
    # check_all 中 "" in name 恒真导致过滤失效。strip + 滤空段。
    if args.filter:
        font_filter = [f.strip() for f in args.filter.split(",") if f.strip()]
        font_filter = font_filter or None
    else:
        font_filter = None
    installed, missing = check_all(font_filter)

    print_status(installed, missing)

    if args.source_dir and missing:
        print()
        scan_and_copy(args.source_dir, missing, args.yes)
    elif missing:
        print_install_guide(missing)


if __name__ == "__main__":
    main()
