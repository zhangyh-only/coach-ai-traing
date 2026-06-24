---
description: 后向沉淀指定业务域的设计文档（扫代码→docs/feature-specs/<domain>.md）
argument-hint: <业务域，如 auth / billing / 订单>
---

显式触发 **feature-spec** skill，对业务域 `$ARGUMENTS` 做后向设计沉淀。

## 这是什么

feature-spec 是**后向**（as-built）的：扫现有代码，把该域**现在**怎么搭的（功能设计、数据流转、业务流程）记成长期文档，落到 `docs/feature-specs/$ARGUMENTS.md`。

与 openspec 分工：openspec 是**前向**（intent，这次要建什么/改什么），feature-spec 是**后向**（已建成什么）。方向相反，不抢活——一句话：openspec 答"该做什么"，feature-spec 答"代码里现在怎么搭的"。

## 怎么做

1. 以**代码为准**扫描该域，禁止凭印象写。
2. 由 skill 判定模式：域文档不存在→新建；用户说"更新/修订"→修订；用户说"重扫/refresh/同步代码"→只刷事实层。
3. 决策（why）**只链接 `docs/adr/` 对应 ADR，不复制**——ADR 是 why 的唯一权威，文档里放链接即可。

若 `$ARGUMENTS` 为空，先让用户在候选业务域里选一个，再开扫。
