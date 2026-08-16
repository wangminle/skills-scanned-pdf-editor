# 脚本参数参考

本文件汇总各脚本的完整参数表，供查阅。工作流与示例见上级 `SKILL.md`；阶段原理、视觉判断、字重匹配深度分析见 `pipeline_methodology.md`。

## scan_edit_ops.py（统一编辑 CLI：删除/移动/替换/复合/提取/封装/验证）

| 子命令 | 功能 |
|---|---|
| `remove` | 删除指定区域（telea / interpolate） |
| `move` | 移动像素块并清理残留 |
| `replace` | 原生供体替换 |
| `compound` | 复合操作：复制源块→清除多个区域→粘贴源块到新位置 |
| `package` | 封装 PDF；替换模式强制做内嵌像素、未修改页哈希和 300dpi 区外变化门禁 |
| `extract` | 用 MuPDF Pixmap 安全提取原生像素并默认做往返封装验证 |
| `export-page` | `extract` 的兼容旧名 |
| `verify` | 像素级验证（变化像素、外框、区外变化、空白行） |

### remove

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 源图片路径 | 必填 |
| `--boxes` | 删除区域 `x1,y1,x2,y2`，可多个（须非负且有序） | 必填 |
| `--method` | `telea`（墨迹蒙版+修补）/ `interpolate`（行间插值填底） | `telea` |
| `--ink-threshold` | 墨迹亮度阈值（<此值为墨迹） | 180 |
| `--dilation` | 墨迹蒙版膨胀核大小 | 5 |
| `--inpaint-radius` | Telea 修补半径 | 5 |
| `--mask-mode` | `ink`=只清理墨迹；`full`=整矩形交给 Telea（残影/污渍区） | `ink` |
| `--noise-sigma` | interpolate 填底微噪点标准差 | 0.45 |
| `--seed` | interpolate 随机种子 | 20260805 |
| `--output` | 输出图片路径 | 必填 |
| `--crop-box` | 额外裁剪预览框 `x1,y1,x2,y2`（逗号分隔） | 无 |
| `--save-mask` | 保存清理蒙版 PNG | 无 |
| `--save-location` | 保存定位标注图 | 无 |

### move

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 源图片路径 | 必填 |
| `--content-x` | 移动区域横向范围 `x1,x2`（须覆盖 `source-y` 带内全部正文墨迹） | 必填 |
| `--source-y` | 移动区域纵向范围 `y1,y2` | 必填 |
| `--shift-y` | 上移像素数（正值=上移；目标越出页面报错） | 必填 |
| `--cleanup-ink-threshold` | 残留清理墨迹阈值 | 246 |
| `--cleanup-mode` | `auto`/`add`/`replace`（语义见下） | `auto` |
| `--cleanup-boxes` | 手动清理框；仅配合 `add`/`replace` | 无 |
| `--output` | 输出图片路径 | 必填 |
| `--crop-box` | 额外裁剪预览框 | 无 |
| `--save-mask` | 保存清理蒙版 PNG | 无 |

清理语义：`--cleanup-mode auto/add/replace` 分别表示仅自动尾部框、自动框追加手动框、仅手动框。
`auto` 与 `--cleanup-boxes` 同时出现会报错，`replace` 没有手动框也会报错。

### replace

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 目标图片路径 | 必填 |
| `--donor-source` | 供体图片路径 | 与 source 相同 |
| `--donor-box` | 供体词块框 `x1,y1,x2,y2`（须完整落在供体图内） | 必填 |
| `--remove-boxes` | 目标清理框，可多个 | 必填 |
| `--destination` | 供体贴入左上角 `x,y`（贴入区须完整落在目标图内） | 必填 |
| `--reference-box` | 目标行参考字框（暗度匹配，须完整落在目标图内） | 必填 |
| `--feather` | 羽化宽度（`<=0` 或宽/高≤2 时硬边） | 4 |
| `--ink-threshold` | 清理墨迹阈值 | 180 |
| `--mask-mode` | `ink`=墨迹蒙版；`full`=整矩形蒙版 | `ink` |
| `--normalize-mode` | `contrast`=对比度缩放；`offset`=纯底色偏移 | `contrast` |
| `--analysis-threshold` | 碰撞/字距/基线分析墨迹阈值 | 220 |
| `--fail-on-collision` | 供体与清理后保留墨迹相交时失败 | off |
| `--min-gap` | 最近墨迹距离下限（像素，不足则失败） | 不阻断 |
| `--max-baseline-deviation` | 相对参考字的最大基线偏差绝对值（像素） | 不阻断 |
| `--output` | 输出图片路径 | 必填 |
| `--crop-box` | 额外裁剪预览框 | 无 |
| `--save-mask` | 保存清理蒙版 PNG | 无 |

每次输出 `placement_analysis` JSON：供体墨迹框、碰撞像素、最近距离、左右字距、
基线和中心偏差。后三个可选阻断参数可将对应指标设为失败门禁。

### compound

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 源图片路径 | 必填 |
| `--content-x` | 内容横向范围（同 move：覆盖 `source-y` 带内全部正文墨迹） | 必填 |
| `--source-y` | 源块纵向范围 `y1,y2` | 必填 |
| `--shift-y` | 上移像素数（正值=上移） | 必填 |
| `--clear-boxes` | 需清除区域 `x1,y1,x2,y2`，可多个（通常含源区域本身） | 必填 |
| `--noise-sigma` | 插值填底噪声 sigma | 0.45 |
| `--seed` | 随机种子 | 20260805 |
| `--output` | 输出图片路径 | 必填 |
| `--crop-box` | 额外裁剪预览框 | 无 |

### verify

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 原图路径 | 必填 |
| `--result` | 编辑后图路径 | 必填 |
| `--allowed-boxes` | 允许变化区域，可多个；给出后区外变化>0 即失败 | 无 |
| `--blank-box` | 空白行残影检查区域（须与图像有交集） | 无 |
| `--blank-thresholds` | 残影检查阈值列表（逗号分隔） | `180,220,240` |
| `--blank-threshold` | 旧单阈值参数（兼容别名，映射到 `--blank-thresholds`） | — |
| `--blank-limit` | 各阈值下空白区深色像素上限 | 0 |
| `--preserve-box` | 应保留不变区域（须与图像有交集） | 无 |

默认同时检查深色（<180）、浅灰（<220）和近纸白（<240）三级残影；
严格交付不要退回单阈值。

### extract / export-page

| 参数 | 说明 | 默认 |
|---|---|---|
| `--pdf` | 源 PDF | 必填 |
| `--output` | 输出 PNG | 必填 |
| `--page-index` | 页码（0-based） | 0 |
| `--as-displayed` | 转到阅读器显示朝向 | off |
| `--audit-dpi` | 往返封装回渲检查 dpi | 300 |
| `--no-roundtrip-check` | 跳过往返验证（不推荐） | off |

### package

| 参数 | 说明 | 默认 |
|---|---|---|
| `--original-pdf` | 给出则替换该 PDF 内嵌图（保留 OCR）；不给则新建单页 PDF | 无 |
| `--page-index` | 替换内嵌图的页码（0-based；越界报错） | 0 |
| `--source-orient` | 输入图朝向：`auto`（按尺寸推断，仅 /Rotate 90/270 非正方形可靠）、`displayed`（`extract --as-displayed` 导出的显示朝向图）、`embedded`（内嵌朝向）。**/Rotate=180 或正方形图尺寸无法区分朝向，`auto` 退出码 2，须显式指定**（BUG-066） | auto |
| `--page-size` | 新建模式页面点尺寸 `W,H`（须两正数） | 按 `--dpi` 推算 |
| `--dpi` | 新建模式推算页面尺寸的 dpi（须正整数） | 300 |
| `--title` | 新建模式 PDF 标题元数据 | 无 |
| `--subject` | 新建模式 PDF 主题元数据 | 无 |
| `--audit-allowed-boxes` | 显示朝向提取图坐标中的允许修改区；替换模式默认必填 | 必填 |
| `--audit-dpi` | 区外变化回渲检查 dpi | 300 |
| `--audit-padding` | 掩模允许区边缘扩展像素 | 2 |
| `--skip-render-audit` | 显式跳过区外回渲门禁；另两项门禁仍执行 | off |

## locate_content.py（行带 / 字框 / 供体定位）

| 子命令 | 功能 |
|---|---|
| `lines` | 纵向墨迹投影检测行带 |
| `glyphs` | 搜索区墨迹连通域 → 字级候选框 |
| `donors` | 按参考框高宽容差搜索供体候选 |

## measure_layout.py（可复核版式测量）

| 子命令 | 输出 |
|---|---|
| `lines` | 行带顶底、行高、前行间距、行顶距离、墨迹率 |
| `ink-bbox` | 区域墨迹最小外接框和墨迹像素数 |
| `gap` | 两框碰撞、水平/最近距离、垂直重叠、基线/中心差 |
| `shift` | 源/目标墨迹框及顶端、基线、中心移动量 |

四个命令均输出 JSON，默认墨迹阈值 220，可直接保存进过程记录。

## verify_outputs.py（JSON 配置驱动验证）

| 参数 | 说明 | 默认 |
|---|---|---|
| `--config` | 验证配置 JSON 文件路径 | 必填 |
| `--strict-hash` | 将 PDF 文件哈希不一致视为失败（不只警告） | off |
| `--reproduce` | 基准图或 reproduce_command 重跑结果与终版 PDF 回渲做容差比较（≤10000px / 通道差≤4 / MAE≤0.001） | off |

配置 JSON 的完整 schema 见 `verify_outputs.py --help`。关键默认值：

| 配置键 | 说明 | 默认 |
|---|---|---|
| `render_backend` | 回渲后端：`pymupdf`（与 `extract` / `package` 审计同源的 MuPDF，避免 PDFium 对 JPEG/PNG 容器走不同色彩路径造成全页假差异）或 `pdfium` | `pymupdf` |
| `render_dpi` | 回渲 dpi | 300 |
| `verify_unmodified_pages` | 逐页比较所有未修改页内嵌整页图像素哈希 | `true` |
| `blank_thresholds` | 空白残影检查阈值列表 | `[180, 220, 240]` |
| `blank_dark_limits` | 各阈值独立的深色像素上限（整数=统一值；对象=按阈值字符串逐级设置；兼容旧 `blank_dark_limit`） | 0 |

## scan_text_fusion.py（增加文字）

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 源扫描图（必填） | - |
| `--text` | 要加的文字 | `（实习律师）` |
| `--position X Y` | 文字左上角坐标（必填） | - |
| `--font` | 字体（路径/注册名/文件名） | 本机首个可用 CJK 字体 |
| `--font-index` | ttc 字体索引 | 0 |
| `--font-size` | 字号 | 31 |
| `--ink-color R G B` | 笔画主体色（显式指定时优先于 `--reference-box` 采样） | 不给则采样或默认 90 97 106 |
| `--reference-box` | 框选参考文字自动取样（须非负且有序） | - |
| `--preview-ink` | 预览最终墨色（解析优先级 + 色块图），不生成融合图 | off |
| `--halo-color R G B` | 边缘晕染色 | 178 196 211 |
| `--crop-box X1 Y1 X2 Y2` | 预览裁剪框（空格分隔；不给则按 position 自动估） | 自动估 |
| `--stage` | clean/fusion/halo/all | halo |
| `--scan-style` | clean/rough | rough |
| `--fusion-strength` | 融合粗糙度倍率 | 按 scan-style |
| `--halo-strength` | 蓝灰晕染强度倍率 | 1.0 |
| `--variants` | 生成融合强度对比接触图 | off |
| `--fusion-variants` | 自定义 `--variants` 的强度档（逗号分隔，如 0.25,0.35,0.5） | 按 `--scan-style` |
| `--compare` | 前后对比图 | off |
| `--stroke-shoulder` | 字重肩部混合权重（替换后备建议 0.25） | 0.0 |
| `--core-alpha-scale` | 核心透明度缩放（替换后备建议 0.875） | 0.965 |
| `--seed` | 随机种子 | 20260701 |
| `--output-dir` | 输出目录 | 源图同目录下 `scan_text_fusion_out/` |
| `--output` | 最终文件名（**只能是** `--output-dir` 内的裸文件名；带路径/绝对路径/`..` 直接拒绝退出码 2——BUG-069 前会静默嵌套落盘） | `<源名>_text_fused.png` |
| `--sample-only X1 Y1 X2 Y2` | 诊断模式：只对参考框取样并打印颜色统计后退出（不生成图） | off |

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

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 源扫描图 | 必填 |
| `--font` | 字体路径 / 注册名 / 文件名（须为上一步识别结果） | 必填 |
| `--font-index` | ttc 索引（仅 `--font` 为显式路径时生效） | 0 |
| `--ref` | 参考字及其框 `字=x1,y1,x2,y2`，可多次给出 | 必填 |
| `--sizes` | 候选字号列表（逗号分隔） | `27,28,29,30,31,32,33,34,35,36` |
| `--thresholds` | 墨迹判定阈值列表（逗号分隔，取中位数共识） | `80,90,100,110,120` |

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
| macOS | 需自行安装（放入 `~/Library/Fonts`） | `Songti.ttc` 多字重（注册表已拆分：SC=Regular[6]、SC Light[3]、SC Regular[6]；文件内另有 Black[0]/Bold[1]/STSong[4]） | `STHeiti Light/Medium.ttc` |

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

## identify_font --candidates 覆盖候选

```bash
python3 scripts/identify_font.py --source page.png --ref 字=x1,y1,x2,y2   --candidates "Songti SC Light=Songti.ttc[3],NotoSansSC=NotoSansSC.ttf"
```

- 每项 `名称=文件名` 或 `名称=文件名[索引]`（`[n]` 指定 ttc 字重索引；不写默认 0）。
- 20260816 复测修复：旧实现硬编码索引 0，多字重家族（如 Hiragino W3/W6）坍缩同分。
- 注册表新收录：`Songti SC Light/Regular`、`STHeiti Light/Medium`、`Noto Sans SC (NotoSansSC.ttf)`。
