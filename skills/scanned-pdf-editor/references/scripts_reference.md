# 脚本参数参考

本文件汇总各脚本的完整参数表，供查阅。工作流与示例见上级 `SKILL.md`；阶段原理、视觉判断、字重匹配深度分析见 `pipeline_methodology.md`。

## scan_edit_ops.py（删除/移动/替换/封装/验证）

| 子命令 | 功能 |
|---|---|
| `remove` | 删除指定区域（telea / interpolate） |
| `move` | 移动像素块并清理残留 |
| `replace` | 原生供体替换 |
| `compound` | 复合操作：复制源块→清除多个区域→粘贴源块到新位置 |
| `package` | 将编辑后的图片封装为 PDF（新建或替换内嵌图） |
| `verify` | 像素级验证（变化像素、外框、区外变化、空白行） |

## scan_text_fusion.py（增加文字）

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 源扫描图（必填） | - |
| `--text` | 要加的文字 | `（实习律师）` |
| `--position X Y` | 文字左上角坐标（必填） | - |
| `--font` | 字体（路径/注册名/文件名） | 本机首个可用 CJK 字体 |
| `--font-size` | 字号 | 31 |
| `--ink-color R G B` | 笔画主体色（显式指定时优先于 `--reference-box` 采样） | 不给则采样或默认 90 97 106 |
| `--reference-box` | 框选参考文字自动取样（须非负且有序） | - |
| `--preview-ink` | 预览最终墨色（解析优先级 + 色块图），不生成融合图 | off |
| `--halo-color R G B` | 边缘晕染色 | 178 196 211 |
| `--stage` | clean/fusion/halo/all | halo |
| `--scan-style` | clean/rough | rough |
| `--fusion-strength` | 融合粗糙度倍率 | 按 scan-style |
| `--halo-strength` | 蓝灰晕染强度倍率 | 1.0 |
| `--variants` | 生成融合强度对比接触图 | off |
| `--compare` | 前后对比图 | off |
| `--stroke-shoulder` | 字重肩部混合权重（替换后备建议 0.25） | 0.0 |
| `--core-alpha-scale` | 核心透明度缩放（替换后备建议 0.875） | 0.965 |
| `--seed` | 随机种子 | 20260701 |
| `--output-dir` | 输出目录 | `./scan_text_fusion_out` |
| `--output` | 最终文件名（`--output-dir` 内的文件名，不是完整路径） | `<源名>_text_fused.png` |

## identify_font.py（字体识别 + 密度交叉验证）

```bash
python3 scripts/identify_font.py --source page.png \
  --ref 字1=x1,y1,x2,y2 --ref 字2=x1,y1,x2,y2
```

除了 NCC 得分排名外，脚本还会做密度交叉验证：计算扫描参考字与渲染字的墨迹密度比，
若差异 >50% 则输出警告（即使 NCC 最高也可能字体不对）。典型场景：原文是仿宋但本机
未安装，误判为宋体（笔画密度约 2 倍）。

## identify_size.py（字号识别）

```bash
python3 scripts/identify_size.py --source page.png --font <字体> \
  --ref 字1=x1,y1,x2,y2 --ref 字2=x1,y1,x2,y2
```

> **联动警告**：`--font` 必须填上一步 `identify_font.py` 识别出的字体。若字体识别
> 结果为"参考/存疑"，先用错误字体识别字号会级联失败（字号偏大/偏小）。解决字体
> 问题后再进入此步。

## align_text.py（垂直对齐）

计算新增文字与原文行对齐的 Y 坐标。不同字体的 ascent/descent 不同，直接用行上沿 Y
会导致墨迹中心偏移。本工具通过墨迹垂直重心匹配计算调整量。

```bash
python3 scripts/align_text.py --source page.png \
  --ref-box 558,557,587,585 \
  --font "仿宋" --size 32 --text "（实习律师）" --y 554
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 源扫描图（必填） | - |
| `--ref-box` | 原文行参考字框 `x1,y1,x2,y2`，可多次给出 | 必填 |
| `--font` | 新增文字字体（路径/注册名/文件名） | 必填 |
| `--font-index` | ttc 字体索引 | 0 |
| `--size` | 字号（与 `scan_text_fusion --font-size` 一致） | 必填 |
| `--text` | 新增文字内容 | 必填 |
| `--y` | 原始计划的 Y 坐标 | 必填 |

`--font` 接受三种写法：完整路径、注册名（如 `仿宋`）、纯文件名。注册名/文件名会经
`font_registry.find_font()` 解析成真实路径与 ttc 索引（注册名匹配大小写不敏感）；
`--font-index` 仅当 `--font` 是显式路径时生效。找不到字体时报错退出（码 2），不再像旧版
那样因 `ImageFont.truetype` 报 `cannot open resource` 而崩在渲染步骤。`--ref` 框须非负且有序。

## font_registry.py（跨平台字体注册表）

`--font` 接受三种写法：完整路径、注册名（如 `仿宋` / `songti`）、纯文件名。不给时按正文优先级
（仿宋 > 宋体 > STSong > …）取本机首个可用 CJK 字体。注册名模糊匹配大小写不敏感。

FONT_DIRS 覆盖 Windows / macOS / Linux 常见目录，包括 macOS 用户级 `~/Library/Fonts`
（双击字体文件"为我安装"的默认落点）和网络共享 `/Network/Library/Fonts`。macOS 上安装
字体后无需额外配置即可被识别。

| 系统 | 仿宋 | 宋体 | 黑体 |
|---|---|---|---|
| Windows | `C:/Windows/Fonts/simfang.ttf` | `C:/Windows/Fonts/simsun.ttc` | `C:/Windows/Fonts/simhei.ttf` |
| macOS | 需自行安装（放入 `~/Library/Fonts`） | `Songti.ttc`（需识别确认 index） | - |

> **字体缺失时**：先用 `check_fonts.py` 检查安装状态并获取安装引导（见下文）。
> `identify_font.py` 也会在置信度不足（参考/存疑）且有未安装候选时提示
> 可能因目标字体缺失。公文/法律文书正文常见仿宋（`simfang.ttf`），
> 若本机未安装，合成字会偏粗偏黑、NCC 也到不了"确定"。安装后重跑即可。

## check_fonts.py（字体环境检查与安装引导）

检查本机 CJK 字体安装情况，对缺失字体提供平台特定的安装方法，支持从指定目录自动复制。

| 参数 | 说明 | 默认 |
|---|---|---|
| `--filter` | 只检查匹配的字体（逗号分隔，如 `仿宋,宋体`） | 全部 |
| `--source-dir` | 从指定目录查找缺失字体并复制到本机字体目录 | 不复制 |
| `--yes` / `-y` | 复制时跳过确认提示 | 需确认 |

```bash
# 查看安装状态
python3 scripts/check_fonts.py

# 从挂载的 Windows 分区自动复制缺失字体
python3 scripts/check_fonts.py --source-dir /Volumes/Windows/Windows/Fonts --yes

# 只检查仿宋
python3 scripts/check_fonts.py --filter 仿宋
```

Windows 系统字体（simfang.ttf 等）为微软专有，合法使用前提是你拥有 Windows 许可。
从自己的 Windows 机器复制到 macOS/Linux 用于本工具是合理的使用方式。
开源替代（Noto CJK / Source Han）可通过 Homebrew 安装，但笔画粗细可能与原文不完全匹配。
