# Git 忽略规则加固设计

## 目标

补齐项目级 `.gitignore`，覆盖常规操作系统临时文件、IDE 本地配置、Python 环境与临时产物，同时避免误忽略可复现构建所需的依赖锁文件和示例环境配置。

## 方案

在现有 Python 模板规则基础上增补三组规则：

1. macOS/Windows 临时文件：`.DS_Store`、`Thumbs.db`、`Desktop.ini`。
2. IDE 本地状态：`.idea/`、`.vscode/`、`.cursor/`，并保留可提交的共享配置例外空间。
3. 环境变量文件：忽略 `.env.*`，但用 `!.env.example` 保留模板；现有 `.env` 规则继续保留。

不忽略 `poetry.lock`、`Pipfile.lock`、`uv.lock` 等依赖锁文件，以便项目需要时纳入版本控制。

## 验证

- 用 `git check-ignore -v` 验证代表性环境、Python 临时和操作系统临时文件均被忽略。
- 用 `git check-ignore` 验证 `.env.example` 不被忽略。
- 用 `git status --short --ignored` 确认当前 `.DS_Store` 不再作为未跟踪文件出现。
- 用 task-list CLI 检查任务台账结构和摘要未被破坏。
