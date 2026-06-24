---
description: 一键脚手架一个 openspec change（proposal + tasks + spec-delta）
argument-hint: <变更简述，一句话说清要建什么>
---

你要为本项目脚手架一个新的 openspec change。`$ARGUMENTS` 是用户给的变更简述。

## 前置检查
1. 确认 `openspec/`（含 `openspec/changes/`、`openspec/specs/`）存在。**不存在就停下**，提示：
   > openspec 尚未初始化。请先运行 `npx openspec init`（或全局 `openspec init`），再回来执行 /rig:new-change。
   不要自行创建 openspec 骨架。
2. `$ARGUMENTS` 为空时，先问清楚这次要建什么，拿到一句话简述再继续。

## 推导 change id
- 从简述提炼一个 kebab-case id：动词开头、3-5 个词、全小写连字符（如 `add-oauth-login`、`split-billing-service`）。
- 若 `openspec/changes/<id>/` 已存在，追加 `-2`、`-3` 避免覆盖。

## 生成文件
在 `openspec/changes/<id>/` 下建以下三件套。**范围必须明确、验收必须可执行**——这是这个命令存在的意义，宁可逼用户当场把边界和验收说清，也不要写空话。

### proposal.md
> **必须含 `## Why` 与 `## What Changes` 两个标题**——`openspec validate`/`archive` 按这两个标题校验，漏了会告警。
```markdown
# <change id>

## Why
<为什么现在要做：触发的问题 / 需求 / 痛点，1-3 句，给出可判断的事实>

**目标（可验证，每条能回答"怎么算做完了"）：**
- <目标 1>
- <目标 2>

## What Changes
**改这些：**
- <明确列出会动的模块 / 文件 / 接口>

**不改这些（显式排除，防止范围蔓延）：**
- <明确列出本次不碰的部分>

## 为什么这样设计
<关键取舍与理由：为什么选这个方案而非替代方案；跨域的长期决策在归档时毕业到 docs/adr/，这里只记本次提案级的 why>
```

### tasks.md
```markdown
# Tasks — <change id>

- [ ] <实现任务 1>
- [ ] <实现任务 2>
- [ ] 写可执行验收：把上面"目标"翻成可运行的断言（测试用例 / 脚本 / `verify-local.sh` 步骤），跑通即视为达成
- [ ] 自验证通过后，用 /rig:archive-change 把 spec delta 合并进 openspec/specs/
```

### specs/&lt;capability&gt;/spec.md
- `<capability>` 取受影响的能力域名（kebab-case，如 `auth`、`billing`），与简述对应。
- 每条需求用 **"系统应当（SHALL）…"** 句式——**`openspec validate` 要求需求文本含 `SHALL` 或 `MUST` 关键字**（纯中文"应当"它识别不了），可判定、不含糊。

```markdown
# <capability> — spec delta

## ADDED Requirements

### Requirement: <一句话需求名>
系统应当（SHALL） <可验证的行为描述>。

#### Scenario: <场景名>
- **当** <前置条件 / 触发>
- **则** <可观察的预期结果>
```
> delta 只写本次的增量，用 `## ADDED / MODIFIED / REMOVED Requirements` 三类标题。改已有需求用 MODIFIED 并写出修改后全文；删除用 REMOVED。

## 收尾
1. 列出已创建的文件路径。
2. 提醒用户：
   - 把 proposal 的范围和验收**再过一遍**，占位符 `<…>` 全部替换为真实内容；
   - 可跑 `openspec validate <id>`（若装了 openspec CLI）检查结构；
   - 实现必须落在本 change 范围内，完成并自验证后用 /rig:archive-change 归档。
