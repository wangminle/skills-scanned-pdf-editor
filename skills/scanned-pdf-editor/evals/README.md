# scanned-pdf-editor 行为级 eval

三类评测验证 skill 的行为契约：

## 1. 触发测试 (trigger)

检查 SKILL.md 描述与真实提示词的匹配度。验证：
- **正例**：涉及扫描版 PDF 删除/移动/替换/增加/复合操作的提示词应触发技能
- **负例**：与扫描 PDF 编辑无关的提示词不应触发
- **description 覆盖**：正例用例的 `keywords` 至少有一个须出现在 SKILL.md frontmatter `description` 中（否则触发测试名存实亡）

匹配规则：prompt 同时含"扫描/PDF/扫描件"类词 + "删除/移动/替换/增加/编辑/修改"类词。

## 2. 行为测试 (behavior)

用合成扫描件图执行 CLI 命令，验证行为契约：
- **remove**：输出尺寸不变、框外无变化、框内墨迹被清除
- **remove --mask-mode full**：整矩形被清理
- **move**：输出尺寸不变、目标位置出现内容
- **compound**：源块被清除、目标位置出现源块内容
- **replace**：输出尺寸不变、目标区域有新内容
- **replace --normalize-mode offset**：offset 与 contrast 模式产生不同输出；contrast 对照运行失败（非零退出码/无输出）计为失败，不假绿

## 3. 基线对比 (baseline)

记录无 skill 时常见做法的缺陷，验证 skill 确实覆盖了这些缺陷：
- **BASE-001**：直接 PIL 粘贴不做归一化/羽化/验证
- **BASE-002**：删除文字只用 Telea 不做墨迹蒙版/框外裁回
- **BASE-003**：增加文字不识别字体字号、不做扫描融合

## 运行

```bash
cd evals && python3 run_evals.py              # 摘要输出
cd evals && python3 run_evals.py --verbose     # 详细输出
cd evals && python3 run_evals.py --filter trigger   # 只跑触发测试
cd evals && python3 run_evals.py --filter behavior  # 只跑行为测试
cd evals && python3 run_evals.py --filter baseline  # 只跑基线对比
```

## 文件结构

```
evals/
├── eval_cases.json   # eval 用例定义
├── run_evals.py      # 运行器（确定性自检，不跑真实模型）
├── EVAL.md           # 真实模型 with/without-skill 评测指南
├── evals.json        # skill-creator 风格用例（交互式）
└── README.md         # 本文件
```

## 扩展

新增 eval 用例编辑 `eval_cases.json`，新增类别在 `run_evals.py` 添加对应的运行函数。
