---
description: 把刚踩的坑/教训沉淀成 lesson，并按"三级进化"引导晋升为 convention 规则或 lint 检查（每级人工确认）
argument-hint: [可选：这次踩的坑/教训一句话]
---

把这次踩的坑沉淀下来，让它"踩一次、永久兜底"。教训：$ARGUMENTS

这是 harness "越用越聪明"的入口。机制是**三级进化**，每一级晋升都要**你确认**——防止把一次偶然或错误的经验扩散成规则。**不臆造**：只记真实发生过的坑；信息不全先问我，别编。

## 一级 · lesson（单次记录）
把这次的坑追加进 `docs/lessons.md`（不存在就新建）。**这个文件不会被注入上下文**——它只是沉淀台账，避免原始 lesson 污染每次编码窗口（只有晋升后的规则才进注入路径）。每条按这个结构写：

```
## <一句话教训>
- 日期：<今天>
- 触发场景：<什么操作 / 什么上下文下发生的>
- 现象：<踩了什么坑、报什么错>
- 根因：<为什么会这样>
- 对策：<下次怎么避免；尽量写成可执行的判断>
- 出现次数：1
- 状态：lesson
```
若 `$ARGUMENTS` 为空，先问我这次要记什么坑，再写。

## 二级 · pattern（复现归纳）
写之前先扫一遍 `docs/lessons.md`：这次的坑和已有某条是否同源？
- 是 → 不新增；把那条的「出现次数」+1，把「对策」从具体个例**归纳成更一般的规则陈述**（去掉项目 / 个例细节），状态改 `pattern`，并告诉我"这是第 N 次，已归纳为 pattern"。
- 否 → 停在 lesson。

## 三级 · 晋升（instinct → 进规则，**必须先问我**）
当一条已是 `pattern`、且值得在**所有**同类场景强制时，按它属于哪桶提出晋升方案，**给出确切 diff、等我确认后再落**：
- **A 桶（机器可判：命名 / 路径 / 禁某调用 / 依赖方向…）** → 提议在 `scripts/lint-one.sh`（必要时配 linter 配置）加一条检查，让它在改完文件时被 `lint-changed` 自动拦。最硬的兜底。（Java「方法/类必有 Javadoc」这类 presence 规则接 checkstyle 靶向硬闸的现成范式，见 rig 的 `reference/recipes/java-checkstyle-javadoc.md`。）
- **B 桶（需判断：语义 / 风格 / 归属…）** → 提议在项目 `docs/conventions/code.md` 或 `structure.md` 加一行（会被 `inject-conventions` 在编码时注入）。仅当这条坑**跨项目都成立**，才提议进全局 `~/.claude/conventions.md`（注入所有项目）。

晋升后：把 `docs/lessons.md` 里那条状态改 `instinct`，并注明晋升去向（哪条 lint / 哪份 conventions），原 lesson 条目保留作审计链。

## 边界
- 晋升**复用现有机制**：A 桶进 `lint-one.sh`（已被 `lint-changed` 跑）、B 桶进 `docs/conventions/`（已被 `inject-conventions` 注入）——**不新增任何 hook**。
- 全程不替我决定晋升、不擅自改 `conventions` / `lint-one.sh`；每级都先给我看。
- 不执行 git 提交。
