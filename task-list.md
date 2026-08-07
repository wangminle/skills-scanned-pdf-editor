# 任务跟踪列表

记录本项目所有任务：代码 bug、bug 转需求、新增需求、需求调整、功能开发、代码审查、测试数据、文档维护、配置运维等。

> 说明：本文件是当前项目的任务清单。所有新增事项、状态变更和完成记录都应同步写入本文件。
> 字段说明：动作字段只允许以下 8 个固定枚举：修复、开发、优化、调整、规划、检查、文档、运维。
> 时间说明：发现时间和完成时间分开记录，格式为 YYYY-MM-DD HH:MM，使用机器本地时区的 24 小时制时间；未完成事项的完成时间填 -。
> 状态说明：Bug 未完成用待修复，通用未完成用待办（或待开发），进行中/已完成/已修复/已关闭/已解决按语义选用；条目互引用 [[BUG-001]] 语法。
> 归并规则：审计、复核、核查、审查、验证、评估统一记为“检查”；重构、清理统一记为“优化”；方案、梳理统一记为“规划”；记录类文档事项统一记为“文档”。

## 代码 Bug

| ID | 动作 | 问题描述 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-001 | 修复 | stroke_shoulder_blend 和 core_alpha_scale 在文档中标注为必需但 scan_text_fusion.py 未实现 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已修复 | 见 [[ADJ-001]]；make_text_mask / render_scan_fusion / render_halo 均加入可选参数 |
| BUG-002 | 修复 | PDF 封装有 save_image_as_pdf / replace_pdf_image 函数但无 CLI 子命令 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已修复 | 见 [[ADJ-002]]；新增 package 子命令支持两种模式 |
| BUG-003 | 修复 | 缺少 requirements.txt 依赖清单文件 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已修复 | 创建 scripts/requirements.txt，README 改为 pip3 install -r 引用 |
| BUG-004 | 修复 | verify_outputs.py --reproduce 语义错误：比的是源 PDF vs 终版，而非「基准图/管线重跑结果 vs 终版回渲」；真实编辑几乎必失败、源≈终又会误报通过 | 2026-08-05 19:40 | 2026-08-05 19:53 | 已修复 | 泛化实现见 [[ADJ-004]]；e2e 验证 pass/fail/command/未配置四条路径；严格像素比对在 --reproduce 模式下跳过 |
| BUG-005 | 修复 | ink_mask_in_boxes 用浮点 luma 阈值化，与原项目 cv2 整数灰度在阈值边界不一致（复现对比 G1），每区域约 2k 蒙版像素差，阻碍旧任务逐像素复现 | 2026-08-05 19:45 | 2026-08-05 19:50 | 已修复 | 改用 cv2.cvtColor(COLOR_RGB2GRAY) 整数灰度；test_skill 29 项仍全过 |
| BUG-006 | 修复 | identify_size.py --font 只接受路径，不接受注册名/文件名；SKILL.md 第 3 步示例在 macOS 报 cannot open resource（复现对比 G4） | 2026-08-05 19:45 | 2026-08-05 19:51 | 已修复 | 走 font_registry.find_font（路径/注册名/文件名三写法）；找不到清晰报错退出码 2；Songti SC 冒烟通过 |
| BUG-007 | 修复 | test_package_cli 只测新建 PDF 模式，未覆盖 --original-pdf 替换内嵌图模式 | 2026-08-05 19:40 | 2026-08-05 19:52 | 已修复 | 见 [[TST-004]] |
| BUG-008 | 修复 | scanned-pdf-editor 放在项目根目录 skills/，未安装到 Codex/Claude 可发现的技能目录，当前会话无法自动触发 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已关闭 | 用户决定暂不安装；可发现路径为 ~/.agents/skills、~/.zcode/skills（用户级）或 <repo>/.agents/skills、<repo>/.zcode/skills（工作区级）。需安装时再处理 |
| BUG-009 | 修复 | identify_size.py 对空白/无墨迹参考框仍返回字号 27 并错误标记“确定” | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 共识计算前预检最低阈值墨迹，无墨迹参考框报错退出码 3；见 [[TST-005]] |
| BUG-010 | 修复 | replace_pdf_image 未创建输出父目录，--original-pdf 模式写入新建嵌套目录时报 FzErrorSystem | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 保存前 output_path.parent.mkdir(parents=True)；与 save_image_as_pdf 行为一致；见 [[TST-005]] |
| BUG-011 | 修复 | verify_outputs.py 将终版页数硬编码为 1 且只回渲第 1 页，无法验证 package --page-index 支持的多页 PDF | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 新增 expected_pages/page_index 配置（默认 1/0 兼容旧配置），按目标页回渲与取尺寸；见 [[TST-005]] |
| BUG-012 | 修复 | ink_mask_in_boxes 在区域内取墨迹后直接膨胀，蒙版和 Telea 修改会越过用户给定 boxes | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 膨胀后 cv2.bitwise_and(mask, region) 裁回越界部分；框外蒙版/改动归 0、框内仍清理；见 [[TST-005]] |
| BUG-013 | 修复 | replace_pdf_image 对含多张图片的页面静默替换 images[0]，可能替换 logo/印章而非整页扫描图 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 新增 _select_page_image_xref 按页面覆盖面积比例选最大图；多图头部并列时 strict 报错；见 [[TST-005]] |
| BUG-014 | 修复 | README 要求用 pytest 自测，但 requirements.txt 未声明 pytest | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | requirements.txt 增 pytest>=7.0（注释标为测试依赖） |
| BUG-015 | 修复 | font_registry.FONT_DIRS 未收录 ~/Library/Fonts（macOS 用户级字体目录），导致 macOS 双击安装 simfang.ttf 后 skill 仍找不到字体，add 路线无法复现（复现对比 task002add 字体 bug） | 2026-08-05 20:15 | 2026-08-05 20:25 | 已修复 | 新增 ~/Library/Fonts + /Network/Library/Fonts；resolve_font 验证可找到该目录下文件；见 [[ADJ-006]] [[CHK-007]] |
| BUG-016 | 修复 | identify_size.py 用最低阈值 min(thresholds)=80 做无墨迹预检，把只有较浅有效墨迹（如灰度 100、在阈值 120 下有效）的参考框误判为空白并退出 | 2026-08-05 20:53 | 2026-08-05 20:55 | 已修复 | 改为 max(thrs) 最宽松阈值预检；注释纠正为”thr 越高越宽松”；ink_dims(crop,80) 无墨迹但 ink_dims(crop,246) 有 1600px 不再误拒；见 [[TST-010]] [[CHK-011]] |
| BUG-017 | 修复 | remove_regions_interpolate 页面边缘采样不足时仍可能读到空平滑窗口，NaN 转 uint8 后把删除区部分填成纯黑 | 2026-08-05 20:53 | 2026-08-06 00:46 | 已修复 | 上下邻域样本行数 ≠ target_h 时用 cv2.resize 线性插值到目标高度再平滑；CHK-012 复现 (0,0,40,80)/(0,5,40,95) 零值通道=0、无 empty-slice 警告；task007 仍 bit-exact；见 [[TST-011]] |
| BUG-018 | 修复 | evals/evals.json 中多处中文引号未做 JSON 转义，文件无法解析，与 CHK-009”符合 schema”结论矛盾 | 2026-08-05 20:53 | 2026-08-05 20:55 | 已修复 | 中文文本内 ASCII 双引号替换为中文引号””；python3 -m json.tool 验证合法；新增 test_evals_json_is_valid 回归测试；见 [[TST-010]] [[CHK-011]] |
| BUG-019 | 修复 | test_skill.py 中 3 个测试用相对路径调用 identify_size.py / verify_outputs.py，从父目录运行 pytest 时找不到脚本文件 | 2026-08-06 01:10 | 2026-08-06 01:10 | 已修复 | 改为 Path(__file__).parent / “脚本名” 绝对路径；58 passed 从任意 CWD 均通过；见 [[CHK-015]] |
| BUG-020 | 修复 | move_block / move_and_clear：目标 y 越顶时，或负切片静默绕到页底（source_y=(100,130) shift_y=150 → 块落 250–279），或混合正负切片 ValueError 崩溃（如 shift_y=120/150 对更高块） | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | move_block/move_and_clear 越界校验：目标 y 越顶/越底时 ValueError 报错，不再负切片绕底；合法路径 bit-exact；见 [[TST-012]] |
| BUG-021 | 修复 | normalize_donor_patch contrast 模式对全墨迹/纯色供体 donor_contrast=0 → ZeroDivisionError 裸崩，无引导 | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | normalize_donor_patch contrast 模式加 donor/target 对比度下限守卫（<1.0 报错并提示 offset）；见 [[TST-012]] |
| BUG-022 | 修复 | remove_regions_interpolate：框超出图像边界或零高度（y1==y2）时 fill 与切片 shape 不一致 → broadcast ValueError；框未裁进图像 | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | remove_regions_interpolate 框裁剪到图像边界内，越界框只填可见部分、全外框跳过；合法路径 bit-exact；见 [[TST-012]] |
| BUG-023 | 修复 | paste_donor_patch / replace_with_donor：destination 使贴入区超出右下时底图切片小于供体/羽化蒙版 → broadcast ValueError | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | paste_donor_patch 贴入前校验目标区域完整落在图内，越界报清晰错误；合法路径 bit-exact；见 [[TST-012]] |
| BUG-024 | 修复 | cmd_package --page-size 只给 1 个值或非数字时裸 IndexError/ValueError，无清晰参数错误 | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | cmd_package --page-size 解析加 try/except，校验 len==2/有限/正数，非法退出码 2；见 [[TST-012]] |
| BUG-025 | 修复 | scan_text_fusion：sample_ink_color 零面积/倒置参考框 → NaN→ValueError；save_with_crop 将含斜杠的 --output 当文件名时未建中间目录（scan_edit_ops 嵌套 --output 已有 mkdir） | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | sample_ink_color 空 ROI 守卫（报错提示坐标/尺寸）；save_with_crop 改 ensure_dir(full.parent) 建子目录；见 [[TST-012]] |
| BUG-026 | 修复 | evals/run_evals.py check_differs_from_contrast：args_c.index("--normalize-mode") 在三元赋值中先求值，无该参数时 ValueError；同文件 F401/E702 | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | run_evals.py check_differs_from_contrast 加合约检查（无 normalize-mode 时返回明确失败原因）；移除 F401 import os；见 [[TST-012]] |
| BUG-027 | 修复 | run_checks.sh ruff 门禁只查 scripts/，漏掉 evals/，导致 [[BUG-026]] 漏过“ruff 全清”结论 | 2026-08-06 11:30 | 2026-08-06 12:23 | 已修复 | run_checks.sh ruff check . -> .. 覆盖 evals/；见 [[TST-012]] [[OPS-004]] |
| BUG-028 | 修复 | parse_box 不校验坐标顺序：倒置/空框（如 x2&lt;x1）静默接受，后续空切片导致删除等操作无效果 | 2026-08-06 11:46 | 2026-08-06 12:23 | 已修复 | parse_box 加坐标顺序校验：x1>=x2 或 y1>=y2 时 ArgumentTypeError 报错；合法框不受影响；见 [[TST-013]] |
| BUG-029 | 修复 | feather_mask(edge=0) 除零：角点/边缘 distance=0 处 NaN、其余为 1；edge&lt;0 时 alpha 全 0（供体静默丢失）。--feather 0 非可靠硬边 | 2026-08-06 11:46 | 2026-08-06 12:23 | 已修复 | feather_mask edge<=0 时返回全 1 硬边蒙版，避免除零 NaN；合法 edge>0 路径 bit-exact；见 [[TST-013]] |
| BUG-030 | 修复 | save_image_as_pdf 不校验 page_size：0/负数仍写出 PDF，无友好报错 | 2026-08-06 11:46 | 2026-08-06 12:23 | 已修复 | save_image_as_pdf 封装前校验 page_size 有限且为正数，0/负/NaN 报 ValueError；合法路径 bit-exact；见 [[TST-013]] |
| BUG-031 | 修复 | smooth_noise 在 1×1（max==min）时归一化除零，产生 NaN 中间态后经 uint8 静默退化；极小 mask 理论可触发 | 2026-08-06 11:46 | 2026-08-06 12:23 | 已修复 | smooth_noise 退化形状（max==min）时返回零场，避免归一化除零 NaN；合法形状 bit-exact；见 [[TST-013]] |
| BUG-032 | 修复 | _select_page_image_xref：全部内嵌图 rect 为空时 ratio 全 0，strict 仅在 best_ratio&gt;0.5 且头部接近时报错，故静默返回无效 xref | 2026-08-06 11:46 | 2026-08-06 12:23 | 已修复 | _select_page_image_xref 全空 rect（best_ratio=0）时 RuntimeError 报错，不再静默返回无效 xref；正常多图不受影响；见 [[TST-013]] |
| BUG-033 | 修复 | move_block / move_and_clear：倒置或零高 source_y（y1≥y2）仍通过 BUG-020 越界守卫；空移动后自动 cleanup 仍静默改图（探针：source_y=(60,40)/(40,40) 改 522px） | 2026-08-06 12:35 | 2026-08-06 12:44 | 已修复 | 库函数校验 x1&lt;x2、y1&lt;y2；CLI 新增 parse_ordered_pair 用于 --content-x/--source-y；见 [[TST-014]] [[CHK-021]] |
| BUG-034 | 修复 | run_evals check_differs_from_contrast：仅检查 `--normalize-mode` 键存在，主跑已是 contrast 时仍做 contrast↔contrast，失败文案误报「offset 与 contrast 输出相同」 | 2026-08-06 12:35 | 2026-08-06 12:44 | 已修复 | 校验取值 ≠ contrast，否则返回合约失败原因；见 [[TST-014]] |
| BUG-035 | 修复 | cmd_package 无 --page-size 时用 `--dpi 0` 推算 page_size → ZeroDivisionError 裸崩（BUG-024/030 未覆盖 dpi 回退路径） | 2026-08-06 12:35 | 2026-08-06 12:44 | 已修复 | dpi≤0 时 stderr 清晰错误并 exit 2；见 [[TST-014]] |
| BUG-036 | 修复 | _select_page_image_xref 不去重 xref：同一图片在页面放置两次时 get_images 返回重复条目，strict 模式误报「覆盖比例最高的两个过近」，replace --original-pdf 不可用 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | 按 xref 去重后再评分；重复 xref [5,5] 去重后正常返回 5；见 [[TST-015]] [[CHK-023]] |
| BUG-037 | 修复 | parse_box 不拒绝负坐标，numpy 负索引静默回绕：remove/move/verify/sample_ink_color/identify 参考框等切片路径把操作移到错误区域且全程无报错 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | parse_box 加非负校验；identify_font.parse_ref 同步加非负+有序校验；见 [[TST-015]] [[CHK-023]] |
| BUG-038 | 修复 | move_block / move_and_clear 只校验 y 方向越界（BUG-020），x2 超宽被静默截小、x1<0 回绕为空块，cleanup 仍执行并报告成功 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | move_block/move_and_clear 补对称 x 方向校验（x1<0 或 x2>img_w 报错）；见 [[TST-015]] [[CHK-023]] |
| BUG-039 | 修复 | cmd_verify 的 --blank-box/--preserve-box 完全越界时切片为空，blank/preserved 计数为 0，验证对未检查任何像素的框报告「验证通过」 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | cmd_verify 裁剪框到图像边界后判交集为空即 exit 1；blank_region_dark_pixels 空框报错；见 [[TST-015]] [[CHK-023]] |
| BUG-040 | 修复 | replace 的 donor_box/reference_box 越界不校验：部分越界时供体被静默截小贴不满目标区；完全越界时抛误导性「未找到暗色墨迹」 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | replace_with_donor 入口校验 donor_box⊂供体图、reference_box⊂底图，越界 ValueError；见 [[TST-015]] [[CHK-023]] |
| BUG-041 | 修复 | verify_outputs.py 源/终版页尺寸不一致时 image_diff 抛 ValueError 裸 traceback：错误不归档到用例、后续全部用例被跳过、已记录的错误也不输出 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | verify 渲染后先比 shape 短路报错；main 逐用例 try/except 归档异常不崩；见 [[TST-015]] [[CHK-023]] |
| BUG-042 | 修复 | run_evals.py check_differs_from_contrast 不检查对照运行返回码：contrast 运行失败时整个 diff 块被跳过，BEH-006 假绿 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | contrast 对照运行检查 returncode≠0 与输出缺失，失败显式判失败；见 [[TST-015]] [[CHK-023]] |
| BUG-043 | 修复 | identify_font.py 只有一个已装候选字体时 second_score=0，margin=总分必然达标，均分≥0.6 即误判「确定（明显领先）」，且抑制「目标字体可能未安装」提示 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | len(ranked)<2 时判「参考（仅一个已装候选）」，不抑制安装提示；见 [[TST-015]] [[CHK-023]] |
| BUG-044 | 修复 | font_registry.find_font 注册名模糊匹配大小写敏感：find_font("Songti") 命中而 find_font("songti") 返回 None，与文件名匹配的 lower() 行为不一致 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | 改为 spec_l in name.lower()，注册名/文件名匹配均大小写不敏感；见 [[TST-015]] [[CHK-023]] |
| BUG-045 | 修复 | render_halo 内联的噪声归一化未同步 BUG-031 守卫：1×1 退化输入 max==min 除零产生 NaN，经 uint8 转换静默归零 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | render_halo 内联归一化加 span==0 守卫返回零场；见 [[TST-015]] [[CHK-023]] |
| BUG-046 | 修复 | 次要缺陷打包：feather_mask 宽/高≤2 时 alpha 全零供体静默丢失；多处 CLI 解析裸 traceback（--boxes 未挂 type=、--fusion-variants/--candidates 尾逗号、--ref 坐标个数错）；identify_size 偶数阈值中位数 int() 截断；identify_font 重复 --ref 同字静默覆盖；render_pdf_page/pdf_page_info 的 pypdfium2 句柄未关闭 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | feather 维度≤2 返回全 1；CLI main 集中捕获 ArgumentTypeError/ValueError exit 2；parse_ref 显式校验；fusion-variants 过滤空段；中位数改 round；重复 ref 警告；pdfium 句柄 try/finally close；见 [[TST-015]] [[CHK-023]] |
| BUG-047 | 修复 | run_evals.py trigger_match 从不使用加载的 SKILL.md description 与用例 keywords 字段：删掉 description 里全部触发词，8 项触发 eval 仍全绿，触发测试名存实亡 | 2026-08-07 10:10 | 2026-08-07 11:20 | 已修复 | run_trigger_evals 增 keyword 覆盖校验：正例 keywords 须至少一个出现在 description 中，否则 FAIL；TRG-005 keywords 补移动/删除；见 [[TST-015]] [[CHK-023]] |
| BUG-048 | 修复 | replace_pdf_image 的 fitz 文档句柄不在 try/finally 中，异常时泄漏文件描述符（与 BUG-046 的 render_pdf_page/pdf_page_info 同族但遗漏了此处）；且 page_index 无越界校验，fitz 负索引回绕到末页，静默替换错误页面 | 2026-08-07 12:30 | 2026-08-07 12:45 | 已修复 | 加 try/finally 关闭 document；page_index 越界 IndexError；见 [[TST-016]] [[CHK-025]] |
| BUG-049 | 修复 | verify_outputs.py render_case_page 的 pymupdf 后端同样缺 try/finally 和 page_index 校验（与 BUG-048 同族），pdfium 路径已在 BUG-046 修复但 pymupdf 路径被遗漏 | 2026-08-07 12:30 | 2026-08-07 12:45 | 已修复 | pymupdf 路径加 try/finally 关闭 document；page_index 越界 IndexError；见 [[TST-016]] [[CHK-025]] |
| BUG-050 | 修复 | identify_size.py --ref 解析用 r.split('=') / box.split(',') 无校验：缺等号、坐标个数错、负坐标回绕均产生裸 traceback 或静默错位（与 BUG-037 同族），identify_font.parse_ref 已有完整校验但此处未对齐 | 2026-08-07 12:30 | 2026-08-07 12:45 | 已修复 | 新增 parse_ref 函数与 identify_font.parse_ref 对齐（格式/个数/整数/非负/有序校验）；见 [[TST-016]] [[CHK-025]] |
| BUG-051 | 修复 | scan_text_fusion.py --reference-box / --sample-only / --crop-box 用 type=int nargs=4 直接接收，负坐标在 numpy 切片 / PIL crop 中静默回绕或截断到错误区域（与 BUG-037 同族） | 2026-08-07 12:30 | 2026-08-07 12:45 | 已修复 | 新增 validate_box 校验非负+x1<x2+y1<y2，三处调用点均接入；见 [[TST-016]] [[CHK-025]] |
| BUG-052 | 修复 | render_pdf_page (pypdfium2) 默认不应用页面 /Rotate 旋转：page.render(rotation=None) 等价于 rotation=0，有 /Rotate 的 PDF 渲染结果方向可能错误（端到端测试 task001 发现：页面 /Rotate=270，默认渲染为 portrait 1655×2341，显式 rotation=270 才输出 landscape 2341×1655） | 2026-08-07 20:30 | 2026-08-07 22:00 | 已修复 | 修复：render_pdf_page 增加 page.get_rotation() 并传 rotation=rotation 给 render()；测试 test_render_pdf_page_applies_rotation 验证旋转后方向正确；见 [[TST-018]] [[PLN-003]] |
| BUG-053 | 修复 | scan_text_fusion.py --reference-box 静默覆盖 --ink-color：同时指定两参数时 ink_color 被 sample_ink_color 返回值替换，--help 未说明此优先级，深墨色扫描件自动采样值融合后偏浅（task002 差值 15.8→手动指定深墨色后 0.5） | 2026-08-07 20:30 | 2026-08-07 22:00 | 已修复 | 修复：--ink-color default 改为 None，run() 实现三级优先（显式 > 采样 > 默认）；同时新增 --preview-ink 诊断模式；测试 test_ink_color_explicit_overrides_reference_box / test_ink_color_reference_box_when_no_explicit 验证；见 [[TST-018]] [[PLN-003]] |
| BUG-054 | 修复 | 根 README.md 残留 evals 引用（ADJ-007 已删 evals/ 但未同步根 README）：目录树 2 处仍列 evals/、检查命令 `cd ../evals && python3 run_evals.py` 2 处执行即失败、`evals/EVAL.md` 死链 2 处；同节 `pytest test_skill.py` 仍是旧路径（ADJ-008 已移至 tests/scripts/） | 2026-08-07 21:09 | 2026-08-07 21:18 | 已修复 | 中英目录树删 evals 行、docs/ 改 design/；检查节删 evals 命令与死链，pytest 路径改为仓库根 tests/scripts/；见 [[CHK-030]] |
| BUG-055 | 修复 | skill README.md L19 自测命令相对路径错误：`cd scripts` 后 `pytest ../../tests/scripts/test_skill.py` 解析为 skills/tests/（不存在），已实测报 No such file；应为 ../../../tests/scripts/test_skill.py | 2026-08-07 21:09 | 2026-08-07 21:18 | 已修复 | ../../→../../../（与 SKILL.md 写法对齐）；见 [[CHK-030]] |
| BUG-056 | 修复 | 安装目录（~/.agents/skills、~/.claude/skills 两处）未同步本轮改动：缺 align_text.py / check_fonts.py，SKILL.md / identify_font.py / scan_edit_utils.py / scan_text_fusion.py 均为旧版——BUG-052/053 修复与 PLN-003 全部新工具在安装副本中不生效 | 2026-08-07 21:09 | 2026-08-07 21:18 | 已修复 | rsync -a --delete 镜像同步，diff -rq 校验两处与源完全一致；align_text/check_fonts/scripts_reference 均已就位；见 [[CHK-030]] |
| BUG-057 | 修复 | SKILL.md 膨胀至 579 行，超过项目多次引用的 skill-creator <500 行约束（DOC-010/011 记录 468/471 行 <500）；本轮新增第 1.5/5 步与 check_fonts/align_text 两节所致 | 2026-08-07 21:09 | 2026-08-07 21:18 | 已修复 | 工具参考节（129 行完整参数表）下沉至 references/scripts_reference.md，SKILL.md 保留速查+链接，579→461 行 <500；见 [[CHK-030]] |
| BUG-058 | 修复 | BUG-052「修复」把 `page.get_rotation()` 当作 pypdfium2 `render(rotation=)` 的附加旋转传入，对 `/Rotate` 90/270 页与内嵌 XObject 像素不一致（实测 Rotate=270：回渲与 embedded MAE≈71、顶底色条对调）；单测只断言宽高假绿；`package --original-pdf` / replace 可能写错朝向 | 2026-08-07 21:14 | 2026-08-07 21:56 | 已修复 | 根因：PDFium 的 FPDF_GetPageWidthF/HeightF 已返回旋转后尺寸，render() 内部已应用 /Rotate，rotation 参数是附加旋转；传 get_rotation() 等于双重旋转。改为 rotation=0，让 PDFium 自行处理 /Rotate。用真实 Rotate=270 扫描件验证：修复后 pypdfium2 与 fitz 渲染方向一致（MAE=3.6）；测试改为内容朝向断言（黑块位置）而非宽高；见 [[CHK-032]] |
| BUG-059 | 修复 | `font_registry.find_font` 注册名用 `spec_l in name.lower()` 子串匹配过宽：`"Song"`/`"song"`/`"宋"`→仿宋 simfang，`"SC"`→Songti，`"GB"`→Hiragino，`"serif"`→Noto Serif；identify/fusion/align/size 静默选错字体 | 2026-08-07 21:14 | 2026-08-07 21:56 | 已修复 | 新增 `_name_tokens()` 把注册名拆成语义段（仿宋/FangSong/Songti/SC），匹配规则改为 token 精确/前缀（≥2 字符）+ 文件名精确/词干；中文走 token 路径（"宋"不是"仿宋"前缀不再误命中）；19 项匹配用例全部正确；见 [[CHK-032]] |
| BUG-060 | 修复 | `scan_text_fusion` `--fusion-strength nan`：argparse `type=float` 接受 NaN，API 产出全黑图（min=max=0）仅 RuntimeWarning、CLI rc=0；负数 strength 在 API 层 `rng.normal(scale<0)` 裸 ValueError | 2026-08-07 21:14 | 2026-08-07 21:56 | 已修复 | main() 渲染前统一校验 fusion/halo/stroke-shoulder/core-alpha-scale 四参数有限且非负，nan/inf/负数 parser.error 退出码 2；见 [[CHK-032]] |
| BUG-061 | 修复 | 框坐标未校验 ⊂ 图像：`scan_text_fusion.validate_box` / `align_text --ref-box` 只查非负有序；越界 ROI 静默截断，`--crop-box` 超界时 PIL crop 可扩出黑边；与 BUG-040 同族 | 2026-08-07 21:14 | 2026-08-07 21:56 | 已修复 | validate_box/parse_box/parse_ref(×2) 增加可选 image_size 参数校验框完整落在图内；run()/诊断模式/align main/identify main 调用点均传入图像尺寸；向后兼容（不传则不查越界）；见 [[CHK-032]] |
| BUG-062 | 修复 | `check_fonts.py --filter` 裸 `split(",")`：尾逗号产生空串，`"" in name` 恒真导致过滤失效（`--filter 仿宋,` 列出远多于 `--filter 仿宋`）；带空格写法也会匹配失败 | 2026-08-07 21:14 | 2026-08-07 21:56 | 已修复 | main() 的 filter 解析改为 strip + 滤空段；CLI 实测 `--filter 仿宋` 与 `--filter 仿宋,` 输出行数一致；见 [[CHK-032]] |

## 调整事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| ADJ-001 | 调整 | scan_text_fusion.py 参数化：--stroke-shoulder / --core-alpha-scale 可选参数，默认值保持 add 模式 bit-exact | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 修复 [[BUG-001]]；test_stroke_shoulder_default_preserves_old_behavior 验证一致性 |
| ADJ-002 | 调整 | scan_edit_ops.py 新增 package 子命令（ReportLab 新建 PDF + PyMuPDF replace_image 保留 OCR 层） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 修复 [[BUG-002]]；--original-pdf / --page-size / --dpi / --page-index 参数 |
| ADJ-003 | 调整 | verify_outputs.py 新增 --reproduce 复现模式（内存重渲 + 三阈值容差检查） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 修复 [[BUG-003]] 相关中等缺口；REPRODUCE_MAX_CHANGED_PIXELS=10000 |
| ADJ-004 | 调整 | verify_outputs.py --reproduce 泛化：配置支持 reproduce_command（shell 重跑）+ reproduce_image，缺省回退 expected_image 基准图 | 2026-08-05 19:40 | 2026-08-05 19:53 | 已完成 | 修复 [[BUG-004]]；docstring / 示例配置同步加 reproduce_command / reproduce_image 字段 |
| ADJ-005 | 调整 | 补齐删除项目原脚本中的整矩形 Telea 清理、纯底色偏移归一化、task007 复制后清除复合流程 | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | G2: full_mask_in_boxes + remove_regions_telea(mask_mode="full") + replace_with_donor(mask_mode=) + CLI --mask-mode；G3: normalize_donor_patch(mode="offset") + paste_donor_patch/replace_with_donor(normalize_mode=) + CLI --normalize-mode；G6: move_and_clear() + compound 子命令；SKILL.md 模式 B+ 文档；见 [[TST-008]] [[CHK-008]] |
| ADJ-006 | 调整 | identify_font.py 置信度不足（参考/存疑）且有未安装候选时，提示目标字体可能缺失并给出安装路径；无已装字体时也报错引导 | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | 三路径验证：确定不提示、参考/存疑提示安装路径、无已装字体报错+引导 exit 1；见 [[BUG-015]] |
| ADJ-007 | 调整 | 移除 evals/ 目录：用户决定 skill 质量通过实际 CLI 使用验证，无需单独 eval 测试（tests/ 测试用例不随 skill 安装到用户环境，eval 引用外部文件无实际价值） | 2026-08-07 14:00 | 2026-08-07 19:15 | 已完成 | 删除 evals/ 全部文件（eval_cases.json/evals.json/run_evals.py/EVAL.md/README.md）；run_checks.sh ruff check .. -> .；README.md 移除 evals/ 行；test_skill.py 移除 7 项 evals 依赖测试 + 3 个 _load_run_evals 辅助方法，替换 2 项 BUG-027 测试；测试数 159->152；三处安装目录同步更新；见 [[BUG-018]] [[BUG-026]] [[BUG-027]] [[BUG-034]] [[BUG-042]] [[BUG-047]] [[TST-006]] [[TST-009]] |
| ADJ-008 | 调整 | 将 test_skill.py 从 skills/scanned-pdf-editor/scripts/ 移至 tests/scripts/：测试文件属开发层面，不随 skill 安装到用户环境 | 2026-08-07 19:20 | 2026-08-07 19:25 | 已完成 | test_skill.py 中所有 Path(__file__).parent 改为 SCRIPTS_DIR 常量指向 skills 脚本目录；E402 加 noqa；run_checks.sh 用 PROJECT_ROOT 变量定位测试文件；README.md/SKILL.md 更新测试命令路径；三处安装目录同步删除 test_skill.py；152 passed / ruff 全清 / run_checks.sh ✅ |
## 检查事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| CHK-001 | 检查 | 代码审查：文档与实现一致性检查，发现 3 个关键缺口 + 5 个中等缺口 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 关键缺口见 [[BUG-001]] [[BUG-002]] [[BUG-003]]；中等缺口含 --reproduce、示例配置、测试覆盖、文档笔误 |
| CHK-002 | 检查 | 28 项单元测试全部通过验证（原 22 + 新增 6） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | pytest test_skill.py -v -> 28 passed in 0.38s；含 TestScanTextFusionAdvanced 6 项 + test_package_cli |
| CHK-003 | 检查 | 项目全量内容检查：逐文件核对文档/脚本/测试数据/配置，复跑 28 项自测与 CLI/依赖可用性 | 2026-08-05 19:28 | 2026-08-05 19:28 | 已完成 | 28 passed in 0.36s；PyMuPDF 1.27.2 可用；发现 3 处低危卫生问题（parse_boxes 未使用、BytesIO 文件尾导入、__pycache__ 残留），未修复待用户决定 |
| CHK-004 | 检查 | 回归验证：29 项单元测试 + --reproduce e2e（pass/fail/command/未配置四路径）+ identify_size 注册名/错误路径冒烟 | 2026-08-05 19:52 | 2026-08-05 19:53 | 已完成 | 29 passed in 0.59s；reproduce changed=0 pass、40000px fail、command pass、未配置清晰报错；严格像素模式不受影响 |
| CHK-005 | 检查 | 新 skill 二次代码审查：对照两个平行项目，执行单测、静态检查与 4 个边界最小复现 | 2026-08-05 20:01 | 2026-08-05 20:01 | 已完成 | 29 passed；ruff 发现 15 项卫生问题；新增 [[BUG-008]] 至 [[BUG-014]]、[[ADJ-005]]、[[TST-005]]、[[TST-006]]、[[OPT-002]] |
| CHK-006 | 检查 | 修复回归验证：逐个复现 [[BUG-009]] 至 [[BUG-014]] 边界并验证修复，全量测试 37 passed | 2026-08-05 20:11 | 2026-08-05 20:11 | 已完成 | 37 passed（29 原 + 8 新 TestEdgeCaseRegressions）；5 个 PyMuPDF SWIG 弃用警告为既有项；示例配置加载新字段默认值 OK |
| CHK-007 | 检查 | 字体 bug 回归验证：39 项单元测试 + identify_font 三路径功能性验证（确定不提示/参考提示安装/无已装报错引导） | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | 39 passed in 0.75s；确定 NCC=0.978 不提示、参考 NCC=0.965 margin=0.118 提示安装路径、无已装 exit 1+引导 |
| CHK-008 | 检查 | G2/G3/G6 功能 + 行为级 eval 回归验证：48 项单元测试 + 17 项 eval（触发 8 + 行为 6 + 基线 3） | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | 48 passed in 0.88s；17/17 eval 通过；见 [[ADJ-005]] [[TST-006]] [[TST-008]] |
| CHK-009 | 检查 | 6 个 PDF 任务对照验证 + skill-creator 规范合规检查 | 2026-08-05 20:45 | 2026-08-05 20:48 | 已完成 | 6 任务 G1-G6 缺口全部修复；quick_validate.py 通过；SKILL.md 455 行 <500；后二次复查确认 quick_validate 不检查 evals.json，原“符合 schema”结论错误，见 [[BUG-018]] [[CHK-010]] |
| CHK-010 | 检查 | 修复后二次复查：逐项回归 BUG-008～BUG-015、全量单测/eval/静态检查、skill 结构校验与新增边界最小复现 | 2026-08-05 20:53 | 2026-08-05 20:53 | 已完成 | 48 passed、现有 run_evals 17/17、quick_validate 通过；但新增 [[BUG-016]]～[[BUG-018]]，ruff 仍有 19 项，现有”触发/基线 eval”不是真实模型对照，见 [[TST-009]] [[OPT-003]] |
| CHK-011 | 检查 | BUG-016～018 修复后回归验证：全量单测 54 项 + evals 17 项 + evals.json JSON 合法性 + 6 PDF 任务复验 | 2026-08-05 20:55 | 2026-08-05 20:58 | 已完成 | 54 passed（48 原 + 6 新 TestBugFix016_018）；17/17 eval 通过；evals.json json.loads OK；task001/003/004/006/007 像素差 ≤4 无黑块；task002add 仍缺 simfang.ttf（环境限制非代码 bug）；见 [[BUG-016]] [[BUG-017]] [[BUG-018]] [[TST-010]] |
| CHK-012 | 检查 | 第三次修复复查：全量单测、JSON/eval、ruff、skill 校验及 BUG-016～018 扩展边界复现 | 2026-08-05 23:43 | 2026-08-05 23:43 | 已完成 | 54 passed、evals.json 合法、现有确定性 eval 17/17、quick_validate 通过；BUG-016/018 通过，[[BUG-017]] 大面积贴边框复现仍失败（随后在 00:46 关闭）；ruff 19 项，[[TST-009]] [[OPT-003]] 仍待办 |
| CHK-013 | 检查 | BUG-017 完整修复回归：CHK-012 最小复现 + TST-011 + 全量单测 + task007 bit-exact | 2026-08-06 00:46 | 2026-08-06 00:46 | 已完成 | (0,0,40,80)/(0,5,40,95) zero=0、无 empty-slice 警告；58 passed；task007 identical=True；见 [[BUG-017]] [[TST-011]] |
| CHK-014 | 检查 | 收尾验证：ruff 全清 + 回归门禁 run_checks.sh + 确定性 eval + EVAL.md 真实模型评测脚手架 | 2026-08-06 00:59 | 2026-08-06 00:59 | 已完成 | ruff check . → All checks passed（18→0）；run_checks.sh 通过；确定性 eval 17/17；evals/EVAL.md 含 6 用例源/基准映射+with/without-skill 流程+评分记录模板；见 [[OPT-003]] [[TST-009]] |
| CHK-015 | 检查 | 续接会话验证：从父目录运行 pytest 发现 3 个路径相关测试失败，修复后全量回归 | 2026-08-06 01:10 | 2026-08-06 01:10 | 已完成 | 发现 [[BUG-019]]（相对路径改绝对路径）；58 passed 从任意 CWD 通过；ruff All checks passed；BUG-017 复现 zero=0 无警告 |
| CHK-016 | 检查 | 审查 .gitignore 是否齐全：对照仓库垃圾文件、git check-ignore 与 skill 运行产物风险 | 2026-08-06 11:04 | 2026-08-06 11:04 | 已完成 | 现有缓存/系统/IDE/环境规则已生效；缺口含 Agent 安装目录，见 [[OPS-003]]；tmp/tasks/二进制产物为可选预防项 |
| CHK-017 | 检查 | 全项目 bug 复查：基线回归（58 单测 / eval 17/17 / ruff scripts 通过）+ 探针复现，登记 [[BUG-020]]～[[BUG-027]] | 2026-08-06 11:30 | 2026-08-06 11:46 | 已完成 | 最重 [[BUG-020]] 静默绕底；代码未修 |
| CHK-018 | 检查 | 双清单交叉确认：首轮 probe + 二次审查（parse_box/feather/page_size0/smooth_noise/xref 等）逐项最小复现后入账 | 2026-08-06 11:45 | 2026-08-06 11:47 | 已完成 | 确认 [[BUG-020]]～[[BUG-032]]；BUG-029 收窄为部分 NaN；编号沿用首轮入账，二次项续 [[BUG-028]]+；[[OPS-004]] 与 [[BUG-027]] 同因 |
| CHK-019 | 检查 | BUG-020..032 全量修复回归验证：95 单测 + ruff 全清 + run_checks.sh + evals 17/17 + 合法路径 bit-exact（旧版 vs 新版逐函数对比） | 2026-08-06 11:46 | 2026-08-06 12:23 | 已完成 | 95 passed（80 原+15 新 TestBugFix028_032）；ruff check . 全清；run_checks.sh ✅；evals 17/17；feather/smooth_noise/save_pdf/telea/interpolate/move/replace/fusion/halo 全 bit-exact；见 [[BUG-020]]..[[BUG-032]] [[TST-012]] [[TST-013]] |
| CHK-020 | 检查 | 独立复核 BUG-020..032 修复充分性：复跑门禁 + 边界探针 + correctness/testing 审查 | 2026-08-06 12:31 | 2026-08-06 12:40 | 已完成 | 鲜证据：95 passed、run_checks ✅、evals 17/17；宣称失败模式大多已堵住；残留 [[BUG-033]](P1) [[BUG-034]](P2) [[BUG-035]](P2)；测试缺口见备注（BUG-027 仅字符串锁、BUG-028 assertRaises 过宽、下溢/target_contrast/CLI page-size≤0 等未锁） |
| CHK-021 | 检查 | BUG-033..035 修复回归：106 单测 + ruff + run_checks + evals 17/17；顺带收紧 BUG-027/028 测试并文档化单图空 rect | 2026-08-06 12:41 | 2026-08-06 12:44 | 已完成 | 106 passed；见 [[BUG-033]]..[[BUG-035]] [[TST-014]] |
| CHK-022 | 检查 | 全项目 bug 复查（第五轮）：106 单测基线全过后，5 路并行逐文件审查 + 重点发现亲自复现，登记 [[BUG-036]]～[[BUG-047]] | 2026-08-07 10:10 | 2026-08-07 10:10 | 已完成 | 最重 [[BUG-036]] xref 重复 strict 误报、[[BUG-037]] 负坐标静默回绕（均已复现）；代码未修，待用户决定 |
| CHK-023 | 检查 | BUG-036～047 全量修复回归验证：140 单测 + ruff 全清 + run_checks.sh + evals 17/17 + 逐 bug 行为复验 | 2026-08-07 11:00 | 2026-08-07 11:20 | 已完成 | 140 passed（106 原 + 34 新 TestBugFix036_047）；ruff check . 全清；run_checks.sh ✅；evals 17/17；12 组 bug 逐项行为复验均 FIXED；见 [[BUG-036]]..[[BUG-047]] [[TST-015]] |
| CHK-024 | 检查 | 独立复核 BUG-036～047 是否均已修复：源码逐项对照 + TestBugFix036_047 + 全量单测 | 2026-08-07 11:00 | 2026-08-07 11:00 | 已完成 | 12 项源码修复均在位；TestBugFix036_047 34/34 passed；全量 140 passed；与 [[CHK-023]]/[[TST-015]] 结论一致，待修复=0 |
| CHK-025 | 检查 | 第六轮全项目 bug 复查：140 单测基线全过后逐文件审查，发现 [[BUG-048]]～[[BUG-051]]（fitz 句柄泄漏/越界、coordinate 校验遗漏），修复后全量回归 | 2026-08-07 12:30 | 2026-08-07 12:45 | 已完成 | 159 passed（140 原 + 19 新 TestBugFix048_051）；ruff check . 全清；run_checks.sh ✅；evals 17/17；见 [[BUG-048]]..[[BUG-051]] [[TST-016]] |
| CHK-026 | 检查 | 独立复核 BUG-048～051 是否均已修复：源码逐项对照 + TestBugFix048_051 | 2026-08-07 11:24 | 2026-08-07 11:24 | 已完成 | 4 项源码修复均在位；TestBugFix048_051 19/19 passed；与 [[CHK-025]]/[[TST-016]] 结论一致 |
| CHK-027 | 检查 | 端到端测试结果与期望效果像素级对比：全页一致率、新增文字区域墨色/笔画密度/位置对齐/字体校验 | 2026-08-07 20:30 | 2026-08-07 21:30 | 已完成 | task001：全页一致率 99.90%，原文完全一致，但新增文字 y 重心偏上 4.1px（747 vs 期望 751）--垂直未对齐；task002：全页一致率 99.92%，原文完全一致，但新增文字笔画密度是期望 2 倍（1023 vs 514 暗像素）--字体识别错误（Songti SC NCC 0.355 存疑仍采用）；两个问题均为 skill 能力缺口（无基线对齐工具、字体识别无法处理未安装场景）；详见 [[PLN-003]]；见 [[TST-018]] [[BUG-053]] |
| CHK-028 | 检查 | 原始成功项目（20260630-P图增加实习律师）与当前 skill 版本全面对比审查：分析 SVG 工作流程图、处理方案记录 MD、重构脚本、处理过程、原始文件 5 项资源，与当前脚本逐文件 diff | 2026-08-07 22:00 | 2026-08-07 22:30 | 已完成 | 结论：核心融合数学（render_scan_fusion + render_halo）完全一致；当前版本是原始的严格超集（scan_text_fusion 482->622 行、identify_font 183->320 行、identify_size 87->153 行）；新增 5 个工具（align_text/--preview-ink/密度验证/scan_edit_utils/verify_outputs）+ 修复全部 53 个 Bug；原始项目的 --reference-box 覆盖 --ink-color 坑已修复（BUG-053）；剩余差距为环境（macOS 缺仿宋字体，NCC 0.355 vs 0.816）和流程（未做 fusion/halo 迭代微调），非代码问题；源 PDF MD5 验证一致；见 [[TST-019]] [[PLN-003]] |
| CHK-029 | 检查 | 未提交改动全量复核（19 文件 +317/-3136）：逐 diff 核对 + run_checks.sh 全量回归 + 安装目录 diff，登记 [[BUG-054]]～[[BUG-057]] | 2026-08-07 21:09 | 2026-08-07 21:09 | 已完成 | 代码本身健康：ruff 全清、178 passed、BUG-052/053 与 PLN-003 实现质量好；问题集中在文档与同步：根 README evals 残留 8 处、skill README pytest 路径错、两处安装目录滞后（缺 align_text/check_fonts）、SKILL.md 579 行超 500 约束；另 task-list DEV-007 备注 check_fonts.py「210 行」实为 298 行（小误差未单独立项）；代码未修，待用户决定 |
| CHK-030 | 检查 | 修复 [[BUG-054]]～[[BUG-057]] 并全量回归验证：根 README 清除 evals/docs 残留、skill README 路径修正、SKILL.md 工具参考下沉 references/scripts_reference.md、两处安装目录 rsync 同步 | 2026-08-07 21:18 | 2026-08-07 21:18 | 已完成 | 4 项全部修复：根 README 0 残留（grep 验证）；skill README ../../../ 正确；SKILL.md 579→461 行 <500；两处安装目录 diff -rq 与源完全一致；run_checks.sh ✅（ruff 全清 + 178 passed，5 警告为既有 PyMuPDF SWIG 弃用）；DEV-007 check_fonts.py 行数误差 210→298 已纠正 |
| CHK-030b | 检查 | 评估 design/plans 两份文档（原始项目对比分析 / 测试问题分析和复盘）：事实核查行数表、BUG 归属、阈值与 CLI 设计稿、引用实物、TST-019 时效 | 2026-08-07 21:09 | 2026-08-07 21:09 | 已完成 | 原误标为重复 CHK-030；结论：两文档结构/口径/诚实度均优，核心结论与独立核查一致；问题：对比分析行数表半数不准、~/Library/Fonts 误归 BUG-044；复盘设计稿与实现有漂移；文档未改，待用户决定 |
| CHK-031 | 检查 | 第七轮全项目 bug 复查：178 单测全绿后，Bugbot + 并行代码审查 + 亲自复现；确认 BUG-054～057 已关闭；登记 [[BUG-058]]～[[BUG-062]]（旋转回归最重） | 2026-08-07 21:14 | 2026-08-07 21:14 | 已完成 | 基线 178 passed；Rotate=270 回渲 vs embedded MAE≈71 已复现；find_font Song→simfang、filter 尾逗号、fusion nan→全黑 已复现；代码未修，待用户决定 |
| CHK-032 | 检查 | 修复 [[BUG-058]]～[[BUG-062]] 并全量回归验证：旋转双重旋转根因深挖 + find_font token 化 + fusion 数值校验 + 框越界校验 + filter 空串过滤 | 2026-08-07 21:56 | 2026-08-07 21:56 | 已完成 | 5 项全部修复。BUG-058 根因：PDFium FPDF_GetPageWidthF 已返回旋转后尺寸，render 内部已应用 /Rotate，rotation 参数是附加旋转；真实 Rotate=270 扫描件验证修复后 pypdfium2 与 fitz MAE=3.6（方向一致）。run_checks.sh ✅：ruff 全清 + 195 passed（178+17 新）；两处安装目录 rsync 同步 diff -rq 一致；旧 BUG-044 源码字符串断言已更新为行为断言 |
| CHK-033 | 检查 | 独立复核 [[BUG-058]]～[[BUG-062]]：源码对照 + 行为探针复现 + TestBugFix058_062 | 2026-08-07 22:25 | 2026-08-07 22:25 | 已完成 | 5 项源码修复均在位；独立探针 9/9 PASS（rotation=0、Song≠仿宋、nan/neg/inf→rc2、越界 SystemExit、filter 尾逗号行数一致）；TestBugFix058_062 17/17 passed；ruff 全清。说明：Cursor 沙箱下全量会因 test_cli_source_dir_copies_font 写 ~/Library/Fonts 失败（单独 unrestricted 通过），与 058-062 无关 |

## 测试数据

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| TST-001 | 开发 | TestScanTextFusionAdvanced 新增 6 项融合特性测试（字重肩部效果/核心透明度效果/halo 可见变化/区域限制/默认行为一致性） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 验证 stroke_shoulder_blend=0.25 vs 0.0 输出不同；0.965 vs 0.875 输出不同；默认参数=显式默认值 |
| TST-002 | 开发 | verify_config.example.json 示例验证配置（2 个用例：删除并上移 + 替换原生供体） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | SKILL.md 引用的示例配置文件 |
| TST-003 | 开发 | test_package_cli CLI 封装子命令测试 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 验证 package 子命令两种模式可正常调用 |
| TST-004 | 开发 | test_package_cli_replace_image：覆盖 --original-pdf 替换内嵌图模式（PyMuPDF） | 2026-08-05 19:52 | 2026-08-05 19:52 | 已完成 | 修复 [[BUG-007]]；造带内嵌图 PDF→替换→校验页数/页尺寸；无 PyMuPDF 时 skipTest |
| TST-005 | 开发 | 增加无墨迹参考框、多页 PDF、嵌套输出目录、多 XObject、框边缘膨胀等边界回归测试 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已完成 | TestEdgeCaseRegressions 8 项锁定 [[BUG-009]] 至 [[BUG-013]]；总计 37 passed |
| TST-006 | 开发 | 建立确定性 CLI/关键词自检：触发词规则、6 条 CLI 行为、3 组文档覆盖检查 | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | eval_cases.json 17 项全部通过；该测试不运行模型，也不构成真正的 with-skill/without-skill 基线，真实行为评测另见 [[TST-009]] |
| TST-007 | 开发 | test_font_dirs_includes_macos_user_fonts + test_resolve_font_finds_file_in_temp_dir：验证 ~/Library/Fonts 在 FONT_DIRS 且 resolve_font 遍历目录查找 | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | 修复 [[BUG-015]]；39 passed（37 原 + 2 新 TestFontRegistry） |
| TST-008 | 开发 | TestCompoundModes 9 项测试：G2 整矩形蒙版 + G3 offset 归一化 + G6 复合操作 + CLI 集成 | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | 见 [[ADJ-005]]；48 passed（39 原 + 9 新 TestCompoundModes） |
| TST-009 | 开发 | 按 skill-creator 规范建立真实模型 with-skill / without-skill 基线运行、断言评分与可审阅结果 | 2026-08-05 20:53 | 2026-08-06 00:59 | 已解决 | 已澄清 skill-creator 规范本身是交互式（逐 prompt 新会话跑+人工审阅，无 grading.json/benchmark 文件格式）。完成脚手架：run_evals.py docstring 诚实改为「确定性自检、不运行模型」；新增 evals/EVAL.md（6 用例源/基准映射、with/without-skill 运行流程、4 维评分表、记录模板）。真实模型逐条运行需人工在新会话执行，填 EVAL.md 记录表，非脚本可一键完成 |
| TST-010 | 开发 | TestBugFix016_018 新增 6 项回归测试：插值全宽/左边缘/右边缘无黑块 + compound 全宽 + identify_size 浅墨迹接受 + evals.json JSON 合法性 | 2026-08-05 20:55 | 2026-08-05 20:55 | 已完成 | 修复 [[BUG-016]] [[BUG-017]] [[BUG-018]]；54 passed（48 原 + 6 新）；见 [[CHK-011]] |
| TST-011 | 开发 | 增加全宽大面积删除框贴近顶部/底部、上下样本总行数小于目标高度的插值回归测试 | 2026-08-05 23:43 | 2026-08-06 00:46 | 已完成 | TestBugFix017LargeEdge 4 项：top-heavy / bottom-heavy / near-full-height / CHK-012 双复现框；断言无 empty-slice 警告、无 NaN、零值通道=0；全量 58 passed；关闭 [[BUG-017]] |
| TST-012 | 开发 | TestBugFix020_027 新增 22 项回归测试：BUG-020 越界移动(3)+BUG-021 零对比度(5)+BUG-022 插值越界(3)+BUG-023 贴入越界(2)+BUG-024 page-size(3)+BUG-025 空ROI/子目录(2)+BUG-026 evals合约(2)+BUG-027 ruff范围(2) | 2026-08-06 11:30 | 2026-08-06 12:23 | 已完成 | 80 passed（含此前 58 原+22 新）；ruff 全清；evals 17/17；见 [[BUG-020]]..[[BUG-027]] |
| TST-013 | 开发 | TestBugFix028_032 新增 15 项回归测试：BUG-028 倒置框(4)+BUG-029 feather除零(3)+BUG-030 page_size校验(4)+BUG-031 smooth_noise退化(2)+BUG-032 空rect(2) | 2026-08-06 11:46 | 2026-08-06 12:23 | 已完成 | 95 passed（80 原+15 新）；ruff 全清；run_checks.sh 通过；evals 17/17；见 [[BUG-028]]..[[BUG-032]] |
| TST-014 | 开发 | TestBugFix033_035 + 测试收紧：倒置/零高 move(4)+parse_ordered_pair(2)+destination 点坐标(1)+evals contrast 合约(1)+dpi≤0(2)+单图空 rect 文档化(1)；BUG-027 非注释命令锁；BUG-028 ArgumentTypeError | 2026-08-06 12:41 | 2026-08-06 12:44 | 已完成 | 106 passed（95 原+约 11 新/收紧）；见 [[BUG-033]]..[[BUG-035]] [[CHK-021]] |
| TST-015 | 开发 | TestBugFix036_047 新增 34 项回归测试：BUG-036 xref去重(1)+BUG-037 负坐标(3)+BUG-038 x越界(4)+BUG-039 越界verify(4)+BUG-040 donor/ref越界(3)+BUG-041 尺寸/异常(2)+BUG-042 源码锁(1)+BUG-043 单候选(1)+BUG-044 大小写(1)+BUG-045 halo退化(1)+BUG-046 feather/median/pdfium/CLI(11)+BUG-047 trigger description(2)；并修正 BUG-013 歧义测试改用不同图 | 2026-08-07 11:00 | 2026-08-07 11:20 | 已完成 | 140 passed（106 原+34 新）；ruff 全清；run_checks.sh ✅；evals 17/17；见 [[BUG-036]]..[[BUG-047]] [[CHK-023]] |
| TST-016 | 开发 | TestBugFix048_051 新增 19 项回归测试：BUG-048 replace_pdf_image try/finally源码锁+负页码+越界页码+合法页码(4)+BUG-049 pymupdf try/finally源码锁+越界页码+合法页码(3)+BUG-050 parse_ref缺等号/坐标个数/负坐标/倒置框/合法值/CLI无traceback(6)+BUG-051 validate_box负坐标/倒置框/合法值/sample-only CLI/reference-box CLI/crop-box CLI(6) | 2026-08-07 12:30 | 2026-08-07 12:45 | 已完成 | 159 passed（140 原+19 新）；ruff 全清；run_checks.sh ✅；evals 17/17；见 [[BUG-048]]..[[BUG-051]] [[CHK-025]] |
| TST-017 | 开发 | tests/测试任务/basic-test-readme.md：task001/task002 集成测试说明（在「田甜」后加「（实习律师）」，保持字体字号扫描效果一致） | 2026-08-07 19:35 | 2026-08-07 19:35 | 已完成 | 描述模式 D 完整操作步骤（渲染->字体->字号->取样->融合->微调->封装）；两任务须各自独立识别字体 |
| TST-018 | 开发 | 端到端测试 task001/task002：调用 skill 完整流程（渲染->OCR定位->字体->字号->取样->融合->封装）在「田甜」后加「（实习律师）」；用户替换 task001 PDF 后重跑；并与期望效果对比 | 2026-08-07 19:27 | 2026-08-07 21:00 | 已完成 | task001: Hiragino Sans GB W6 30px，差异 0.6✅；task002: Songti SC 28px，差异 3.6✅；PDF 打包用 fitz page.replace_image（task001 需旋转图片回 landscape）；发现 [[BUG-052]] [[BUG-053]]。期望效果对比（[[CHK-027]]）：task001 全页一致率 99.90%，新增文字墨色差 1.6（评分 A）；task002 全页一致率 99.92%，新增文字墨色差 8.1、暗像素多 99%（评分 B-，ink-color 调过头偏浓） |
| TST-019 | 开发 | 改进后 skill 端到端复测 task001/task002：使用 align_text.py + --preview-ink + 密度交叉验证 + BUG-052/053 修复后的完整流程重跑 | 2026-08-07 20:30 | 2026-08-07 20:45 | 已完成 | task001（0003）: 墨迹均值差 0.6->0.1（83%提升），一次通过，全页一致率 99.89%；task002（0004）: 墨迹均值差 3.6->0.8（78%提升），迭代 3->0（BUG-053 修复后一次通过），全页一致率 99.89%，y重心差 1.9px；密度交叉验证检测到 task002 密度比 2.11x（仿宋未安装，已知限制）；见 [[PLN-003]] [[TST-018]] [[BUG-052]] [[BUG-053]] |
| TST-020 | 开发 | TestBugFix058_062 新增 17 项回归测试：BUG-058 旋转源码锁+Rotate270内容朝向+Rotate90内容朝向(3)+BUG-059 Song不匹配FangSong+token精确+_name_tokens辅助(3)+BUG-060 nan/负数/inf CLI(3)+BUG-061 validate_box越界/界内/可选/crop CLI/align parse_box(5)+BUG-062 check_all语义+CLI尾逗号+纯逗号(3) | 2026-08-07 21:56 | 2026-08-07 21:56 | 已完成 | 195 passed（178 原+17 新）；ruff 全清；run_checks.sh ✅；旧 BUG-044 源码字符串断言更新为行为断言；见 [[BUG-058]]..[[BUG-062]] [[CHK-032]] |

## 文档维护

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 文档 | SKILL.md 技能文档：四种模式完整说明、参数表、CLI 示例、PDF 封装节 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 含 --stroke-shoulder / --core-alpha-scale / --reproduce / package 参数说明 |
| DOC-002 | 文档 | README.md 快速开始、文件结构、依赖安装说明 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 依赖改为 pip3 install -r scripts/requirements.txt |
| DOC-003 | 文档 | references/pipeline_methodology.md 管线方法论文档（含实现状态注释） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 字重肩部与核心透明度缩放处加实现状态注释 |
| DOC-004 | 文档 | 研究与 skill 设计分析文档编写（能力矩阵、技术路线、架构设计） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 即《扫描版PDF编辑修改_研究与skill设计分析.md》 |
| DOC-005 | 文档 | 分析文档笔误修复：STROKE_SHODER_BLEND→STROKE_SHOULDER_BLEND；scan_edit_ops.py --remove→remove（3处） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | §8.2 字重肩部合并标记为 ✅ 已完成 |
| DOC-006 | 文档 | SKILL.md 修正：封装示例补 scripts/ 前缀（L324 与 L310 不一致）；--reproduce 注释改为基准图/reproduce_command 语义；identify_size --font 三写法说明 | 2026-08-05 19:40 | 2026-08-05 19:51 | 已完成 | 对应 [[BUG-004]] [[BUG-006]] 的文档侧 |
| DOC-007 | 文档 | 明确 scan_text_fusion.py --output 是 --output-dir 内的文件名（非完整路径）；SKILL.md 参数表补 --output-dir/--output 行 + 脚本 help 同步（复现对比 G5） | 2026-08-05 19:45 | 2026-08-05 19:51 | 已完成 | 第 5 步融合示例与工具参考表均已覆盖 |
| DOC-008 | 文档 | SKILL.md font_registry 节补 macOS ~/Library/Fonts 目录说明 + 字体缺失安装指引 blockquote；identify_font.py docstring 同步置信度不足提示 | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | macOS 仿宋行改为"需自行安装（放入 ~/Library/Fonts）"；新增字体缺失提示说明 |
| DOC-009 | 文档 | SKILL.md 参数表补全：remove 表加 --noise-sigma/--seed 行；move 表加 --cleanup-boxes 行并更新 --shift-y 描述 | 2026-08-06 11:30 | 2026-08-06 12:23 | 已完成 | 对应 [[BUG-020]]..[[BUG-027]] 修复涉及的参数文档化 |
| DOC-010 | 文档 | 版本升至 V0.1.1：新增 VERSION/CHANGELOG；同步根 README、skill README、SKILL.md（坐标有序、page-size/dpi/feather、package 参数表）、evals/README；CLI help 对齐 | 2026-08-06 12:45 | 2026-08-06 12:48 | 已完成 | 全称 V0.1.1-Build0178-20260806；SKILL.md 468 行仍 &lt;500；106 passed / run_checks ✅ |
| DOC-011 | 文档 | 版本升至 V0.1.2：VERSION/CHANGELOG 记录 BUG-036～051；同步根 README、skill README、SKILL.md、evals/README、pipeline_methodology（非负坐标、move x、donor 框、feather≤2、单候选字体、page-index、trigger keywords 等） | 2026-08-07 11:17 | 2026-08-07 11:22 | 已完成 | 全称曾用 V0.1.2-Build0179-20260807；后由 [[DOC-012]] 将 VERSION 收为仅 V0.1.2；SKILL.md 471 行 &lt;500；159 passed |
| DOC-012 | 文档 | VERSION 约定改为只记版本号（`V0.1.2`），不再含 Build/日期；同步 CHANGELOG 格式说明与根 README 结构注释 | 2026-08-07 11:30 | 2026-08-07 11:30 | 已完成 | Build/日期仅保留在 CHANGELOG 发布条目标题 |
| DOC-013 | 文档 | 端到端测试问题分析与复盘文档：记录 task001 垂直未对齐、task002 字体识别错误等 5 个问题，提出 5 项 skill 改进方案及实施细节 | 2026-08-07 21:00 | 2026-08-07 21:30 | 已完成 | 文件 design/plans/测试问题分析和复盘-2608.md；含问题数据、根因分析、改进方案、优先级排序；见 [[PLN-003]] [[CHK-027]] |
| DOC-014 | 文档 | 修订复盘文档：同步 BUG-052/053 与改进 1～5 落地状态；统一 vs 原文/期望口径；补充评分标准、验收标准、问题 6 封装朝向；2c 标远期 Spike；保留原方案细节不删减 | 2026-08-07 20:27 | 2026-08-07 20:30 | 已完成 | 同文件 design/plans/测试问题分析和复盘-2608.md；见 [[DOC-013]] [[PLN-003]] |

## 功能开发

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| DEV-001 | 开发 | scan_edit_utils.py 共用工具库：300dpi 回渲、像素块上移、墨迹蒙版、Telea 修补、PDF 封装、差分与中文字体 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | save_image_as_pdf / replace_pdf_image 双模式封装 |
| DEV-002 | 开发 | scan_edit_ops.py 四模式 CLI：remove（telea/interpolate）、move、replace、package | 2026-08-05 19:21 | 2026-08-05 19:52 | 已完成 | 子命令驱动架构；增加文字（add）不在本 CLI，走 scan_text_fusion.py，见 [[DEV-003]] |
| DEV-003 | 开发 | scan_text_fusion.py 扫描融合引擎：字体合成 + alpha 软化 + 蓝灰晕染 + 字重肩部/核心透明度可选参数 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 默认 stroke_shoulder=0.0 / core_alpha=0.965 保持 add 模式 bit-exact 复现 |
| DEV-004 | 开发 | identify_font.py + identify_size.py 字体字号识别（灰度 NCC + 墨迹共识 + 置信度门） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 从增加项目迁移并整合 |
| DEV-005 | 开发 | font_registry.py 字体注册表与跨平台中文字体查找 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 支持 Windows/macOS/Linux 自动选择 |
| DEV-006 | 开发 | verify_outputs.py 验证脚本：严格哈希 + --reproduce 内存复现模式 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 容差：≤10000px / 通道差≤4 / MAE≤0.001 |
| DEV-007 | 开发 | check_fonts.py 字体环境检查与安装引导脚本：检查全部注册 CJK 字体安装状态，对缺失字体提供平台特定安装方法（Windows 字体来源说明 + 开源替代 Homebrew/apt 命令），支持 --source-dir 从挂载的 Windows 分区自动复制字体文件 | 2026-08-07 22:30 | 2026-08-07 23:00 | 已完成 | 新增 scripts/check_fonts.py（298 行）；SKILL.md 增加第 1.5 步「检查字体环境」+ check_fonts.py 工具参考节；README.md 文件结构表同步；9 项单元测试 TestCheckFonts；178 passed / ruff 全清 / run_checks.sh ✅；见 [[CHK-028]] |

## 配置运维

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| OPS-001 | 运维 | 补充项目级 .gitignore，覆盖常规操作系统临时文件、IDE 本地状态、环境变量变体和 Python 打包临时元数据 | 2026-08-06 11:03 | 2026-08-06 11:03 | 已完成 | 保留 .env.example 与依赖锁文件；已执行 git check-ignore 代表性路径验证 |
| OPS-002 | 运维 | 安装 CLAUDE.md 会话结束任务同步规则与 Stop hook，提醒后续 agent 自动维护 task-list | 2026-08-06 11:07 | 2026-08-06 11:07 | 已完成 | 中文规则写入 CLAUDE.md；hook 注册于 .claude/settings.json，脚本为 .claude/hooks/tasklist_sync_reminder.sh；已验证 JSON、可执行权限及单会话去重 |
| OPS-003 | 运维 | .gitignore 增补 Agent 安装目录忽略：.agents/、.claude/、.zcode/ | 2026-08-06 11:09 | 2026-08-06 11:09 | 已完成 | 源码目录 skills/ 不受影响；git check-ignore 验证三条规则生效；见 [[CHK-016]] |
| OPS-004 | 运维 | run_checks.sh ruff 漏查 evals/（与 [[BUG-027]] 同因） | 2026-08-06 11:45 | 2026-08-06 11:47 | 已关闭 | 并入 [[BUG-027]] 跟踪，避免重复；修复时改 run_checks.sh 即可 |
| OPS-005 | 运维 | .gitignore 增补项目运行时产物：scan_text_fusion_out/（默认输出目录）、*.tmp.pdf（replace_pdf_image 异常残留）、tmp/ 与 tasks/（用户任务工作目录） | 2026-08-07 13:00 | 2026-08-07 13:00 | 已完成 | git check-ignore 验证四条规则生效；无已跟踪源文件受影响；见 [[CHK-016]] |
| OPS-006 | 运维 | .gitignore 增补 tests/测试任务/ 忽略规则（大体积测试 PDF 固件，非源码） | 2026-08-07 19:30 | 2026-08-07 19:30 | 已完成 | git check-ignore 验证规则生效；见 [[CHK-016]] [[OPS-005]] |
| OPS-007 | 运维 | .gitignore 增补 tests/results/ 忽略规则；CLAUDE.md 增加端到端测试结果目录说明（文件名格式 yyyymmdd-xxxx-测试事由） | 2026-08-07 19:40 | 2026-08-07 19:40 | 已完成 | git check-ignore 验证规则生效；CLAUDE.md 新增「端到端测试结果目录」节 |
| OPS-008 | 运维 | .gitignore 增补 tests/期望效果/ 忽略规则 | 2026-08-07 19:50 | 2026-08-07 19:50 | 已完成 | git check-ignore 验证规则生效；见 [[CHK-016]] [[OPS-005]] |

## 规划事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| PLN-001 | 规划 | 统一 skill 架构设计：四种操作模式（删除/移动/替换/增加）+ 共用工具层 + 验证层 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | DPI 选择：300 for remove/move/replace，200 for add/fusion；Route A 原生像素迁移 vs Route B 字体合成 |
| PLN-002 | 规划 | 替换优先级链设计：同页词块→同系列页→相同单字→字体合成（含字重肩部） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 优先迁移原生扫描像素，字体合成仅作后备 |
| PLN-003 | 规划 | 端到端测试问题分析与改进方案设计：task001 垂直未对齐、task002 字体识别错误、墨色调参困难、字号连锁失效、PDF 旋转 bug | 2026-08-07 21:00 | 2026-08-07 22:00 | 已完成 | 全部 5 项已实现：①align_text.py 新工具（墨迹垂直重心对齐）②identify_font.py 增加 glyph_fingerprint/rendered_fingerprint 密度交叉验证 ③BUG-053 修复 + --preview-ink 诊断模式 ④SKILL.md 工具链联动警告 ⑤BUG-052 修复；169 测试全通过；详见 design/plans/测试问题分析和复盘-2608.md；见 [[CHK-027]] [[TST-018]] [[BUG-052]] [[BUG-053]] |

## 优化事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| OPT-001 | 优化 | stroke_shoulder / core_alpha_scale 参数化设计：默认值保持 add 模式 bit-exact 复现，替换后备可显式开启 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 避免破坏 seed=20260701 已验证输出；见 [[ADJ-001]] [[BUG-001]] |
| OPT-002 | 优化 | 精简 SKILL.md frontmatter description，只保留触发条件，避免把完整工作流写进描述导致模型跳过正文 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已完成 | description 由约 320 字精简到约 126 字，只留触发条件+授权边界；四模式实现细节仍在正文 |
| OPT-003 | 优化 | 清理 ruff 静态检查问题并把静态检查纳入回归门禁 | 2026-08-05 20:53 | 2026-08-06 00:59 | 已完成 | 清理全部 18 项（E401/E701/E702/F401/F841/E402）；新增 scripts/run_checks.sh（ruff + pytest 回归门禁）；requirements.txt 加 ruff>=0.6；README 文件结构与自测节同步；ruff check . → All checks passed，58 passed |

## 调研事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RES-001 | 规划 | 研究增加项目与删除项目的能力矩阵、技术路线互补性，判断统一 skill 可行性 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 两项目操作完全互补无冲突；输出《扫描版PDF编辑修改_研究与skill设计分析.md》 |
| RES-002 | 规划 | 字体粗细失配原因分析与字重肩部补偿参数研究（来源 task005 实验） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | STROKE_SHOULDER_BLEND=0.25、CORE_ALPHA_SCALE=0.875 为替换后备最佳参数；add 模式用 0.0/0.965 |

## 统计摘要

| 分类 | 总数 | 已完成 | 待开发/待修复 | 完成率 |
| --- | --- | --- | --- | --- |
| 代码 Bug | 62 | 62 | 0 | 100% |
| 调整事项 | 8 | 8 | 0 | 100% |
| 检查事项 | 33 | 33 | 0 | 100% |
| 测试数据 | 20 | 20 | 0 | 100% |
| 文档维护 | 14 | 14 | 0 | 100% |
| 功能开发 | 7 | 7 | 0 | 100% |
| 配置运维 | 8 | 8 | 0 | 100% |
| 规划事项 | 3 | 3 | 0 | 100% |
| 优化事项 | 3 | 3 | 0 | 100% |
| 调研事项 | 2 | 2 | 0 | 100% |
| **总计** | 160 | 160 | 0 | 100% |
