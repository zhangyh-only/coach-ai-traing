---
description: 归档一个已完成的 openspec change，把 spec-delta 合并进 specs，并提示后续沉淀动作
argument-hint: [change-id]（留空则取唯一进行中的 change）
---

把 $ARGUMENTS 指定的 openspec change 归档。$ARGUMENTS 为空时，取当前唯一进行中的 change；若进行中的 change 不止一个，列出来让我选，不要擅自挑一个。

按顺序执行：

## 1. 定位 change
- 运行 `openspec list` 确认 change id 存在且处于进行中状态。
- 找不到、或有歧义（多个候选）就停下来报告，别继续。

## 2. 归档前检查
- 读 `openspec/changes/<id>/tasks.md`，确认所有 task 都已勾选 `[x]`。
- 还有未勾的 task：列出来，问我是真的做完了（去补勾）还是要中止归档。**不要替我勾选。**
- 全部勾选后，运行 `openspec validate <id>`（如可用）确认 spec-delta 格式合法（`## ADDED / MODIFIED / REMOVED Requirements`）。

## 3. 执行归档
- 运行 `openspec archive <id>`，把 spec-delta 合并进 `openspec/specs/`、change 移入归档。
- 命令报错就把原始输出贴给我，不要自行重试或绕过。

## 4. 归档后提示（逐项问我，不替我决定）
归档完成后，明确提醒以下两件事，等我回答：

1. **跨域长期决策 → 毕业成 ADR**
   本次 change 里有没有"为什么这么定"的跨域 / 难回退决策（选型、边界、权衡）？
   有的话用 `/rig:adr` 把它毕业成正式 ADR——它是这类决策"为什么"的唯一权威，feature-spec 只会链接它、不复制。

2. **代码稳定后 → 用 feature-spec 刷新受影响域**
   列出本次改动触及的业务域。提醒我：等代码稳定，用 feature-spec 扫代码把这些域的 `docs/feature-specs/<domain>.md` 刷新到与现状一致（后向沉淀，不是现在立刻做）。

最后用一两句话总结：归档了哪个 change、spec-delta 合并到了哪、待办的 ADR / feature-spec 提示项。
