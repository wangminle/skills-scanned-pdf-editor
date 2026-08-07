# Gitignore 加固 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 补齐项目级 Git 忽略规则，屏蔽常规环境文件、Python 临时文件和跨平台开发机临时文件。

**Architecture:** 保留现有 Python `.gitignore` 模板作为基础，仅在文件末尾增加项目级补充区。环境变量采用“默认忽略、示例显式保留”策略；依赖锁文件不新增忽略规则。

**Tech Stack:** Git ignore pattern、Python task-list CLI、Shell 验证命令。

---

### Task 1: 增补项目级忽略规则

**Files:**
- Modify: `.gitignore`

**Step 1: 添加跨平台临时文件规则**

加入 `.DS_Store`、`Thumbs.db` 和 `Desktop.ini`。

**Step 2: 添加 IDE 本地配置规则**

加入 `.idea/`、`.vscode/` 和 `.cursor/`，避免提交个人编辑器状态。

**Step 3: 添加环境文件规则**

加入 `.env.*` 与 `!.env.example`，保留现有 `.env` 忽略规则。

### Task 2: 同步任务台账

**Files:**
- Modify: `task-list.md`

**Step 1: 记录配置运维事项**

新增 `OPS-001`，记录规则加固范围和验证结果。

**Step 2: 重算统计摘要**

使用 task-list CLI 同步 `统计摘要`。

### Task 3: 验证

**Step 1: 验证代表性路径**

运行 `git check-ignore -v` 检查环境、Python、IDE 和操作系统临时路径。

**Step 2: 验证示例例外**

确认 `.env.example` 不被忽略。

**Step 3: 验证台账**

运行 task-list CLI 的 `check` 和 `summary`，确认无结构错误和摘要漂移。
