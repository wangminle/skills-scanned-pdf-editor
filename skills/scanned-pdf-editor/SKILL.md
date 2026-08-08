---
name: scanned-pdf-editor
description: 对用户有权编辑的扫描版 PDF 或扫描件图片做局部编辑（删除内容、移动位置、替换文字、补录新文字），使修改区域在字体、字号、墨色、纸纹、扫描噪点上与原扫描件像素级一致。仅用于授权且内容真实的场景，不用于伪造或篡改以误导第三方。
version: V0.1.4
---

# 扫描版 PDF 编辑修改（scanned-pdf-editor）

> **版本**：V0.1.4（见仓库根目录 `VERSION` / `CHANGELOG.md`）
> **运行环境**：Python 3.10+

对扫描版 PDF 或扫描件图片做局部编辑，使修改区域在字体、字号、墨色、纸纹、扫描噪点上
与原扫描件保持一致。**仅用于用户有权编辑、且修改内容真实的场景**。

## 何时用 / 何时不用

> **前提**：使用者须对该文书拥有编辑权，且修改内容真实。本技能只做像素级编辑融合，
> 不替使用者承担授权与合规判断。

**用：**
- **草稿修订 / 排版补录**：补漏掉的真实信息、删除多余段落、调整位置、替换措辞。
- **内部材料数字化复原**：纸质内部材料扫描后修订字段，使版面完整。
- **填写或修订用户自有的表单 / 模板 / 协议草稿**。

**不用：**
- **伪造、篡改或隐瞒对文书的修改**，以误导第三方或改变文书的法律 / 证据效力。
- 在**未获授权**的文书上编辑。
- 给**原生电子 PDF**（非扫描）编辑--直接用 Word/PDF 编辑器即可。
- **重绘整页或大面积改图**--本技能每轮只改目标区域。

> 对有法律或证据效力的文书，使用者须按适用规则履行必要的披露 / 留痕义务。

## 处理原则（务必遵守）

1. **只用本地像素合成，不做生成式重绘**--原始页面、印章、正文、版面不被重新生成。
2. **每轮只改动目标区域**--远处像素必须保持原样（输出与源图同尺寸，仅目标区变化）。
3. **优先迁移原生扫描像素**，其次才用字体合成--原生供体同时携带正确的字体、字号、字重、字距、灰度和扫描毛边。
4. **基于参考取样，而非凭感觉**--颜色、质感、对比度以原扫描里风格相近的既有文字为参照。
5. **小步迭代**--每轮只动一两个参数，看裁剪预览再决定。
6. **留痕可追溯**--每个任务目录除最终图外，必须留存过程记录与关键中间产物。

> **坐标约定（全局）**：所有框/区间像素坐标须**非负**且**有序**（`x1<x2`、`y1<y2`）。
> 负值会报错，不会被 numpy/PIL 静默回绕到页尾。
## 四种操作模式

### 模式 A：删除内容

从扫描件中删除指定文字/段落，清除区域不留白色补丁，保留纸张纹理。

**方法一：墨迹蒙版 + Telea 修补**（适合小面积清理）

```
框选删除区域 -> 按亮度阈值提取墨迹 -> 5×5 椭圆膨胀 -> 半径 5 的 Telea 修补
```

只提取墨迹不清空矩形--Telea 修补会利用周围像素填充，保留纸张色差与颗粒。

```bash
python3 scripts/scan_edit_ops.py remove \
  --source page.png \
  --boxes "1197,1665,1288,1718" "1196,2110,1289,2165" \
  --ink-threshold 180 \
  --output page_removed.png \
  --crop-box 900 1550 1500 2680
```

**方法二：行间插值填底**（适合需要彻底清除文字与扫描残影）

```
框选删除区域 -> 用区域两侧纸张底色逐行插值 -> 纵向平滑 -> 加微噪点
```

```bash
python3 scripts/scan_edit_ops.py remove \
  --source page.png \
  --boxes "250,245,2260,335" \
  --method interpolate \
  --output page_removed.png
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `--boxes` | 删除区域列表，每个 `x1,y1,x2,y2`（须非负且 `x1<x2`、`y1<y2`） | 必填 |
| `--method` | `telea`（默认）或 `interpolate` | `telea` |
| `--ink-threshold` | 墨迹亮度阈值（<此值为墨迹） | 180 |
| `--dilation` | 膨胀核大小 | 5 |
| `--inpaint-radius` | 修补半径 | 5 |
| `--mask-mode` | `ink`=只清理墨迹（默认）；`full`=整矩形清理（连背景纸纹一并交给 Telea，适合有残影/污渍的区域） | `ink` |
| `--noise-sigma` | interpolate 方法填底微噪点标准差 | 0.45 |
| `--seed` | interpolate 方法随机种子 | 20260805 |

### 模式 B：移动位置

将一段原生扫描像素块整体移动到新位置（通常用于删除后上移后续正文），不重新排版。

```
测量行基线差确定移动量 -> 复制原生像素块到目标位置 -> 清理原位置的残留墨迹
```

**移动量必须来自实际行带/基线测量**，不能按"约几行"估算。

```bash
python3 scripts/scan_edit_ops.py move \
  --source page.png \
  --content-x 330,2250 \
  --source-y 1735,3070 \
  --shift-y 265 \
  --cleanup-ink-threshold 246 \
  --output page_moved.png \
  --crop-box 120 1320 2350 2200
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `--content-x` | 移动区域横向范围 `x1,x2`（须非负、`x1<x2`，且完整落在图宽内） | 必填 |
| `--source-y` | 移动区域纵向范围 `y1,y2`（须非负、`y1<y2`） | 必填 |
| `--shift-y` | 上移像素数（正值=上移；目标位置越出页面会报错，不会静默绕行） | 必填 |
| `--cleanup-ink-threshold` | 残留清理的墨迹阈值 | 246 |
| `--cleanup-boxes` | 手动指定残留清理区域列表 `x1,y1,x2,y2`（可多个；每框须非负且有序） | 自动取源区域尾部 |

**注意**：移动框只包正文主栏，不得包含页框、页码、印章、批注。

### 模式 B+：复合操作（复制后清除）

task007 类"先复制再清除"的复合流程：保存源块 -> 用插值填底清除多个区域（含源区域本身）-> 粘贴源块到上移位置。与 `move` 的区别：清除用插值填底（整矩形），且可一次清除多个额外区域。

```bash
python3 scripts/scan_edit_ops.py compound \
  --source page.png \
  --content-x 340,2220 \
  --source-y 395,885 \
  --shift-y 82 \
  --clear-boxes "1985,160,2090,235" "250,245,2260,335" "250,330,500,420" "340,395,2220,885" \
  --output page_compound.png
```

`--clear-boxes` 包含所有需要清除的区域（通常含源区域本身 + 其他需清除的区域）。

| 参数 | 说明 | 默认 |
|---|---|---|
| `--source` | 输入图片路径 | 必填 |
| `--content-x` | 内容横向范围 `x1,x2`（源块宽度；须非负、`x1<x2`，且完整落在图宽内） | 必填 |
| `--source-y` | 源块纵向范围 `y1,y2`（须非负、`y1<y2`） | 必填 |
| `--shift-y` | 上移像素数（正值=上移；目标越出页面会报错） | 必填 |
| `--clear-boxes` | 需清除的区域列表（`x1,y1,x2,y2`，可多个；每框须非负且有序） | 必填 |
| `--noise-sigma` | 插值填底的噪声 sigma | 0.45 |
| `--seed` | 随机种子 | 20260805 |
| `--output` | 输出路径 | 必填 |
| `--crop-box` | 额外裁剪预览框 `x1 y1 x2 y2` | 无 |

### 模式 C：替换文字

用新文字替换已有文字。优先使用原生供体，无供体时用字体合成。

**优先级链：同页完整词块 → 同系列页完整词块 → 相同单字 → 字体合成（模式 D）**

#### C-1：原生供体替换

从同页或同系列页找到原生扫描的新文字词块，做对比度归一化后贴入。

```
框选供体词块 -> 对比度归一化（供体纸白/墨迹 → 目标行纸白/墨迹）-> 4px 羽化 -> 贴入
```

```bash
python3 scripts/scan_edit_ops.py replace \
  --source page.png \
  --donor-source donor_page.png \
  --donor-box 787,945,877,997 \
  --remove-boxes "1195,585,1285,637" \
  --destination 1195,585 \
  --reference-box 651,585,696,638 \
  --output page_replaced.png \
  --crop-box 1000 540 1450 670
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `--donor-source` | 供体所在图片（同页则与 source 相同） | 与 source 相同 |
| `--donor-box` | 供体词块框 `x1,y1,x2,y2`（须完整落在供体图内） | 必填 |
| `--remove-boxes` | 目标清理框列表 | 必填 |
| `--destination` | 供体贴入左上角 `x,y`（贴入区须完整落在目标图内） | 必填 |
| `--reference-box` | 目标行参考字框（用于暗度匹配；须完整落在目标图内） | 必填 |
| `--feather` | 羽化宽度（`<=0` 或宽/高≤2 时为硬边全覆盖，不产生 NaN/全零蒙版） | 4 |
| `--mask-mode` | 清理蒙版模式：`ink`=墨迹蒙版（默认）；`full`=整矩形蒙版 | `ink` |
| `--normalize-mode` | 供体归一化：`contrast`=对比度缩放（默认；供体/参考须有足够纸白-墨迹对比度，否则改用 `offset`）；`offset`=纯底色偏移 | `contrast` |

供体只做对比度归一化（或纯底色偏移）和羽化，**不缩放、不锐化、不重新描边**。

#### C-2：字体合成替换（后备）

无原生供体时，用 `identify_font.py` 识别字体 -> `identify_size.py` 识别字号 -> `scan_text_fusion.py` 合成新字。详见模式 D。

合成时**必须**加入**字重肩部**和**核心透明度缩放**，否则会"细、硬、黑"（见 `references/pipeline_methodology.md`）：

```bash
python3 scripts/scan_text_fusion.py --source page.png \
    --text "结案" --position 1202 1669 \
    --font "仿宋" --font-size 42 \
    --ink-color 95 94 98 \
    --scan-style clean --fusion-strength 0.40 \
    --stroke-shoulder 0.25 --core-alpha-scale 0.875 \
    --crop-box 1060 1635 1430 1745
```

| 参数 | 说明 | 替换后备推荐值 | 增加文字默认 |
|---|---|---|---|
| `--stroke-shoulder` | 3×3 MaxFilter 扩张轮廓后混回权重 | 0.25 | 0.0（关闭） |
| `--core-alpha-scale` | 核心透明度缩放 | 0.875 | 0.965 |

这两个参数来自删除项目与 PDF 3 原生"结"字的逐像素对比收敛（边缘像素 423 vs 425，暗核 44 vs 44）。


### 模式 D：增加文字

在扫描件上补录原本不存在的文字，做扫描质感融合。

```
1. 准备源图（200 dpi）
2. 识别字体（灰度 NCC + 密度交叉验证，必做）
3. 识别字号（多阈值共识，须用上一步识别出的字体）
4. 取样参考颜色（--preview-ink 可预览最终墨色）
5. 对齐垂直中心（align_text.py，防止上下偏移）
6. 扫描融合 + 蓝灰晕染
7. 迭代微调
```

> **工具链联动警告**：第 2→3 步有依赖--`identify_size.py` 的 `--font` 必须填第 2 步
> 识别出的字体。若第 2 步给了"参考/存疑"结果，第 3 步用错误字体识别字号会级联失败
> （字号偏大/偏小）。第 2 步不确定时先解决字体问题（安装缺失候选后重跑），不要带着
> 不确定的结果进入第 3 步。

**为什么 200 dpi**：扫描融合的 alpha 上限约 0.93，无法复现极重墨扫描件的暗度；200 dpi 下采样把整页均匀变浅，落在融合可达范围内，自洽。删除/移动/替换用 300 dpi 或内嵌图（纯搬像素需高精度）。

#### 第 1 步：准备源图

```bash
pdftoppm -png -r 200 -f 2 -l 2 "源.pdf" page      # 产出 page-2.png
```

#### 第 1.5 步：检查字体环境（首次使用或换机器时必做）

扫描件原文字体可能与本机已装字体不同。中文公文/法律文书正文常为仿宋（`simfang.ttf`），
macOS 和 Linux 默认不带。**字体缺失是加字效果不符的头号原因**（NCC 偏低、笔画密度 2 倍偏差）。

```bash
python3 scripts/check_fonts.py
```

脚本列出全部已注册 CJK 字体的安装状态，对缺失字体给出平台特定的安装方法。
关键场景：

- **macOS 缺仿宋**：从你的 Windows 机器复制 `simfang.ttf`，双击安装（落到 `~/Library/Fonts/`），
  或用 `--source-dir` 从挂载的 Windows 分区自动复制：
  ```bash
  python3 scripts/check_fonts.py --source-dir /Volumes/Windows/Windows/Fonts --yes
  ```
- **开源替代**：若无法获取 Windows 字体，`check_fonts.py` 也会列出 Homebrew 可装的
  Noto / Source Han 开源字体。注意开源字体与原文可能不完全匹配（笔画粗细有差异）。

> 安装字体后无需重启，直接重跑 `identify_font.py` 即可生效。

#### 第 2 步：识别字体（必做，不可跳过）

**每份扫描件的字体都可能不同，不要沿用上一份任务用过的字体。**

```bash
python3 scripts/identify_font.py --source page.png \
  --ref 田=558,557,587,585 --ref 甜=587,557,614,585
```

判定"确定（明显领先）"才采用，且衬线应明显优于无衬线。
仅有一个已装候选字体时只会给出「参考」，须安装更多候选再交叉验证，或结合文档类型判断。

> **密度交叉验证**：脚本会额外计算扫描参考字与渲染字的墨迹密度比。即使 NCC 最高，
> 若密度差异 >50%（渲染字偏粗/偏细），会输出警告。典型场景：原文是仿宋但本机未安装，
> 误判为宋体（宋体笔画密度约为仿宋 2 倍）。看到此警告时先安装缺失字体再重跑。

#### 第 3 步：识别字号

```bash
python3 scripts/identify_size.py --source page.png --font <上步识别出的字体> \
  --ref 田=558,557,587,585 --ref 甜=587,557,614,585
```

`--font` 可直接填上一步 `identify_font.py` 输出的字体（注册名如 `仿宋`、纯文件名或完整路径均可）。
取中位数共识；置信度门要求 `agree ≥ n−1`。

#### 第 4 步：取样参考颜色

```bash
python3 scripts/scan_text_fusion.py --source page.png \
  --sample-only 315 788 675 835
```

也可用 `--preview-ink` 预览最终墨色（含优先级解析：显式 `--ink-color` > `--reference-box` 采样 > 默认）：

```bash
python3 scripts/scan_text_fusion.py --source page.png \
  --reference-box 315 788 675 835 --preview-ink
```

#### 第 5 步：对齐垂直中心

不同字体的 ascent/descent 不同，直接用行上沿 Y 坐标绘制会导致墨迹中心偏移。
用 `align_text.py` 计算对齐后的 Y：

```bash
python3 scripts/align_text.py --source page.png \
  --ref-box 558,557,587,585 \
  --font "仿宋" --size 32 --text "（实习律师）" --y 554
```

输出调整后的 Y 值，用于下一步 `--position` 的 Y 坐标。

#### 第 6 步：融合加字

```bash
python3 scripts/scan_text_fusion.py --source page.png \
  --text "（实习律师）" --position 617 554 \
  --font "仿宋" --font-size 32 \
  --ink-color 24 25 29 \
  --scan-style clean \
  --crop-box 300 500 850 645
```

#### 第 7 步：迭代微调

看 crop 预览，对照邻近原扫描字，按"调参指引"小步调整。

| 现象 | 调什么 |
|---|---|
| 字形/笔画风格和原字不同 | 字体没对--回第 2 步重新识别 |
| 文字太干净、像数字字体 | `--fusion-strength` 上调 |
| **新字噪点/毛刺比原字多** | 扫描件偏干净--`--scan-style clean`，fusion 降到 0.3~0.5 |
| 颜色偏黑/偏浅 | 重新取样 `--ink-color`，每通道 ±2~4 |
| 缺蓝灰底色感 | `--halo-strength` 上调 |
| 像人工描边、蓝太明显 | `--halo-strength` 下调 |
| 位置偏上/偏下 | 先用 `align_text.py` 计算对齐 Y，再微调 `--position` Y（±2px） |

**关键**：客观噪声指标可能与人眼相反，最终以 crop 人眼对比为准。

## 过程记录（每个任务目录必留）

| 文件 | 内容 |
|---|---|
| `过程记录.md` | 决策链：坐标推导、移动量测量、供体选择、参数选择（带测量值）、试过什么/为何弃 |
| 定位图 | 框选删除/移动/替换区域的标注图 |
| 清理蒙版 | 删除/清理操作的墨迹蒙版 |
| 供体词块 | 替换操作的供体裁剪 |
| 前后对比 | 目标区域处理前后对比 |
| 最终 PNG | 完整结果图 |
| 最终 PDF | 封装后的 PDF |
| PDF 回渲图 | 最终 PDF 的 300dpi 回渲 |
| 字体识别证据（模式 D） | `identify_font.py` 的完整输出 |
| 字号识别证据（模式 D） | `identify_size.py` 的完整输出 |

要点：
- **参数选择要带测量值**--不只写"移动 78px"，要写"相邻正文行距 78px，故删除一行后上移 78px"。
- **试过又弃的方案也要记**，避免下次重蹈。
- 中间产物以 `中间产物_` 前缀，和最终交付物区分。

## 验证

改完后确认以下检查项：

| 检查项 | 方法 |
|---|---|
| 尺寸一致 | 最终图尺寸 == 源图尺寸 |
| PDF 页数 / 页面点尺寸 | 与原始 PDF 一致（不默认 A4） |
| 300dpi 回渲 | 与确认 PNG 逐像素一致 |
| 变化像素数 + 外框 | 与预期值比对 |
| 允许区外变化 | `verify_outputs.py` 检查 = 0 |
| 空白行深色像素 | 亮度 <180 的像素不超过上限；检查框须与图像有交集，否则验证失败 |
| 应保留区域 | 无变化像素；检查框须与图像有交集，否则验证失败 |
| 应删区域深色像素 | 不超过上限 |
| 暗度匹配（模式 D） | 新字 `<100` 均值 vs 参考字 |
| SHA-256 归档完整性 | `verify_outputs.py --strict-hash` |
| 100% 整体 + 300% 细节 | 人工视觉检查 |

```bash
# 像素级验证
python3 scripts/verify_outputs.py --config verify_config.json

# 归档完整性
python3 scripts/verify_outputs.py --config verify_config.json --strict-hash

# 复现容差检查：基准图（expected_image）或配置的 reproduce_command 重跑结果 vs 终版回渲
# （吸收 OpenCV Telea 跨版本/平台舍入差异；不是源 PDF vs 终版，见配置里 reproduce_command/reproduce_image 字段）
python3 scripts/verify_outputs.py --config verify_config.json --reproduce

# 自测
cd scripts && python3 -m pytest ../../../tests/scripts/test_skill.py
```

## PDF 封装

编辑完成后的 PNG 需要封装回 PDF。两种方式：

### 方式一：新建 PDF（PyMuPDF）

适合从整页图新建 PDF，按原始页面点尺寸封装。

```bash
python3 scripts/scan_edit_ops.py package \
    --source page_final.png \
    --output final.pdf \
    --page-size 595.2,841.68 \
    --title "文档标题" --subject "修改说明"
```

不给 `--page-size` 时按 `--dpi`（默认 300）从图像尺寸推算。

| 参数 | 说明 | 默认 |
|---|---|---|
| `--page-size` | 页面点尺寸 `W,H`（须两个有限正数；非法输入退出码 2） | 按 dpi 推算 |
| `--dpi` | 无 `--page-size` 时用于推算；须为正整数（`<=0` 退出码 2） | 300 |
| `--original-pdf` | 若给出则走替换内嵌图模式（保留 OCR）；多图页面按覆盖面积选整页图（同 xref 去重）；全空 rect / 头部并列时会报错 | 无 |
| `--page-index` | 替换模式下的页码（0-based；须在页数范围内，越界报错） | 0 |

### 方式二：替换内嵌图（PyMuPDF，保留 OCR 层）

适合原始 PDF 含 OCR 文字层，只替换整页扫描图。

```bash
python3 scripts/scan_edit_ops.py package \
    --source page_final.png \
    --output final.pdf \
    --original-pdf source.pdf \
    --page-index 0
```

## 工具参考

各脚本的完整参数表、字体注册目录与安装引导见 [`references/scripts_reference.md`](references/scripts_reference.md)。要点速查：

- **scan_edit_ops.py**：`remove` / `move` / `replace` / `compound` / `package` / `verify` 六个子命令（各模式参数见模式 A–C 与 PDF 封装节）。
- **scan_text_fusion.py**：增加/替换文字的融合引擎。关键参数 `--ink-color`（显式 > `--reference-box` 采样 > 默认）、`--stroke-shoulder`、`--core-alpha-scale`、`--preview-ink`。
- **identify_font.py**：NCC 排名 + 墨迹密度交叉验证（密度差 >50% 警告）。
- **identify_size.py**：`--font` 须填上一步识别的字体，否则级联失败。
- **align_text.py**：墨迹垂直重心对齐，算出调整后 Y 给 `--position` 用。
- **font_registry.py**：`--font` 三写法（路径/注册名/文件名），含 macOS `~/Library/Fonts`。
- **check_fonts.py**：CJK 字体安装状态检查 + 平台安装引导 + `--source-dir` 自动复制。

## 调参安全范围

| 参数 | 建议范围 | 单步幅度 |
|---|---|---|
| `--fusion-strength` | 0.3~1.2（干净扫描 0.3~0.5） | ±0.05~0.1 |
| `--halo-strength` | 0.7~1.3 | ±0.05~0.1 |
| `--ink-color`（每通道） | 参考值 ±5 | ±2~4 |
| `--position` Y | 已对齐后尽量不动 | ±2px |
| `--font-size` | 参考字高 ±1 | 1 |
| 供体对比度倍率 | 通常 0.95~1.05 | - |
| 羽化宽度 | 3~5 px | 1 |
| 移动量 | 实测行距 | 不估 |
| 墨迹阈值 | 160~246（视扫描质量） | - |
| 修补半径 | 3~7 | - |

## 详细方法论

阶段原理、视觉判断要点、字重匹配深度分析见 [`references/pipeline_methodology.md`](references/pipeline_methodology.md)。
