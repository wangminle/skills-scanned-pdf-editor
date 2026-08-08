# scanned-pdf-editor

**版本：V0.1.4**（与仓库根目录 `VERSION` / `CHANGELOG.md` 同步）

扫描版 PDF / 扫描件图片的局部编辑技能：删除指定内容、移动正文位置、替换已有文字、补录新增文字，
使修改区域的像素与原扫描件的字体、字号、墨色、纸纹、扫描噪点风格一致。

> 运行环境：**Python 3.10+**。

> 坐标约定：框与区间一律非负且有序（`x1<x2`、`y1<y2`；`--content-x` / `--source-y` 亦同）；
> 负坐标会报错，不会静默回绕。`move` 的内容区须完整落在图内（x/y 均校验）。
> `package --page-size` 须为正数对；无 `--page-size` 时 `--dpi` 须为正整数；
> `--page-index` 须在页码范围内。详情见 `SKILL.md`。

## 快速开始

```bash
cd scripts

# 自测
python3 -m pytest ../../../tests/scripts/test_skill.py -v

# 回归门禁（静态检查 + 单元测试，任一失败即非零退出）
./run_checks.sh

# 删除指定区域
python3 scan_edit_ops.py remove --source page.png \
    --boxes "1197,1665,1288,1718" --output page_removed.png

# 移动像素块
python3 scan_edit_ops.py move --source page.png \
    --content-x 330,2250 --source-y 1735,3070 --shift-y 265 --output page_moved.png

# 原生供体替换
python3 scan_edit_ops.py replace --source page.png \
    --donor-source donor.png --donor-box 787,945,877,997 \
    --remove-boxes "1195,585,1285,637" --destination 1195,585 \
    --reference-box 651,585,696,638 --output page_replaced.png

# 封装为 PDF
python3 scan_edit_ops.py package --source page_final.png --output final.pdf \
    --page-size 595.2,841.68

# 或：保留 OCR 层（替换内嵌图）
python3 scan_edit_ops.py package --source page_final.png --output final.pdf \
    --original-pdf source.pdf

# 验证
python3 scan_edit_ops.py verify --source page.png --result page_edited.png \
    --allowed-boxes "330,1470,2250,3062"

# 泛化验证（JSON 配置驱动，配置格式见 verify_outputs.py --help）
python3 verify_outputs.py --config verify_config.json
python3 verify_outputs.py --config verify_config.json --strict-hash --reproduce

# 增加文字（需先检查字体环境、识别字体和字号）
python3 check_fonts.py
python3 identify_font.py --source page.png --ref 田=558,557,587,585
python3 identify_size.py --source page.png --font simfang.ttf --ref 田=558,557,587,585
python3 align_text.py --source page.png --ref-box 558,557,587,585 \
    --font "仿宋" --size 32 --text "（实习律师）" --y 554
python3 scan_text_fusion.py --source page.png --text "（实习律师）" \
    --position 617 554 --font "仿宋" --font-size 32 --scan-style clean
```

## 依赖

需要 **Python 3.10+**。

```
pip3 install -r scripts/requirements.txt
```

依赖列表见 `scripts/requirements.txt`（已去除 ReportLab；新建 PDF 与替换内嵌图均用 PyMuPDF）。

## 文件结构

```
scripts/
  font_registry.py           跨平台 CJK 字体注册表
  check_fonts.py             字体环境检查与安装引导
  identify_font.py            字体识别（灰度 NCC + 密度交叉验证）
  identify_size.py            字号识别（墨迹共识 + 置信度门）
  align_text.py               垂直中心对齐（墨迹重心计算）
  scan_edit_utils.py          共用工具（渲染、蒙版、修补、移动、替换、差分、验证）
  scan_edit_ops.py            统一 CLI：删除/移动/替换/封装/验证
  scan_text_fusion.py         扫描融合 + 蓝灰晕染（增加文字路线）
  verify_outputs.py           泛化验证框架（JSON 配置驱动）
  run_checks.sh               回归门禁（ruff + pytest）
  requirements.txt            Python 依赖
references/
  pipeline_methodology.md     方法论参考（原理、视觉判断、参数安全范围）
  scripts_reference.md        完整工具参数表（从 SKILL.md 下沉）
SKILL.md                      主文档（四种操作模式 + 工作流）
```

## 来源

整合自两个已验证项目：
- `20260630-P图增加实习律师`：增加文字 + 扫描融合
- `20260720-P图删除一行内容`：删除 + 移动 + 替换 + 验证
