# Git 忽略规则加固

> **日期**：2026-08-06

## 一、目标

补齐项目级 `.gitignore`，覆盖常规操作系统临时文件、IDE 本地配置、Python 环境与临时产物，同时避免误忽略可复现构建所需的依赖锁文件和示例环境配置。

## 二、方案

在现有 Python 模板规则基础上增补三组规则：

1. **跨平台临时文件**：`.DS_Store`、`Thumbs.db`、`Desktop.ini`
2. **IDE 本地配置**：`.idea/`、`.vscode/`、`.cursor/`（保留可提交的共享配置例外空间）
3. **环境变量文件**：`.env.*` 默认忽略，`!.env.example` 显式保留模板

不忽略 `poetry.lock`、`Pipfile.lock`、`uv.lock` 等依赖锁文件，以便项目需要时纳入版本控制。

## 三、执行步骤

### Task 1：增补项目级忽略规则

**修改文件**：`.gitignore`

1. 添加跨平台临时文件规则：`.DS_Store`、`Thumbs.db`、`Desktop.ini`
2. 添加 IDE 本地配置规则：`.idea/`、`.vscode/`、`.cursor/`
3. 添加环境文件规则：`.env.*` 与 `!.env.example`

### Task 2：同步任务台账

**修改文件**：`task-list.md`

1. 新增 `OPS-001`，记录规则加固范围和验证结果
2. 使用 task-list CLI 同步统计摘要

### Task 3：验证

1. 运行 `git check-ignore -v` 验证环境、Python、IDE 和操作系统临时路径均被忽略
2. 确认 `.env.example` 不被忽略
3. 运行 task-list CLI 的 `check` 和 `summary`，确认无结构错误和摘要漂移
