# Changelog

本仓库版本号格式：`V主.次.修订-Build序号-日期`（见根目录 `VERSION`）。

## V0.1.1-Build0178-20260806

相对 V0.1.0（Build0177）的硬化与文档同步：

### 修复（边界输入）

- **BUG-020～032**：越界移动、零对比度供体、插值框裁剪、贴入越界、`--page-size` 非法、空 ROI / 子目录输出、evals 合约、`ruff` 覆盖 `evals/`、倒置框、`feather<=0`、`page_size` 校验、`smooth_noise` 退化、多图空 rect 等
- **BUG-033**：`move_block` / `move_and_clear` 拒绝倒置或零高 `content_x` / `source_y`；CLI 增加 `parse_ordered_pair`
- **BUG-034**：evals `check_differs_from_contrast` 要求主跑为非 `contrast` 的 `normalize-mode`
- **BUG-035**：`package --dpi <= 0` 清晰报错并退出码 2

### 测试与门禁

- 单元测试约 106 项；`scripts/run_checks.sh`（ruff scripts+evals + pytest）；确定性 evals 17/17

### 文档

- `SKILL.md` / README 同步坐标顺序、`page-size` / `dpi` / `--feather` 行为说明
- 本 changelog 与根目录 `VERSION` 文件

## V0.1.0-Build0177-20260806

首个对外标注版本：四模式编辑 skill、CLI、确定性 eval 脚手架与任务台账。
