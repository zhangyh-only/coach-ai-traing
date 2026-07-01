# Coach 提示词结构 + 变量映射 + 接口试跑

诊断的事实基础。三部分：①角色扮演链提示词的分块结构（落点定位用）②随机池变量契约（变量名/字段/注入）③本地业务接口试跑流程。

> 通用版那张"业务 UI 名称↔schema 字段↔Freemarker 注入点"的大表（botAction/maxRounds/phaseProblems/character_profile…）是**百炼 Agent 2.0** 的配置项。**coach 角色扮演链已切回直调模型、不走 Agent 应用**，那套配置项**不适用**——coach 的"阶段/异议/画像"全部写在提示词正文里，不是平台配置。故本文件按 coach 实际重写。

---

## 第一部分：角色扮演链提示词分块结构（落点定位）

线上 SSOT＝各场景目录里的 `最新使用提示词.md`（**受保护**）。结构分块（用户已结构化的版本）：

| 区块 | 业务侧定位说法 | 装什么 | 常见落点坑 |
|---|---|---|---|
| `# 你是谁` → `## 身份信息` | 角色扮演链 → 你是谁 → 身份信息 | Elena 核心人设（27岁武汉白领/爱包舍得花/有主见识货/来线下试背/外部视角顾客） | 人设与性子互相矛盾 |
| `# 你是谁` → `## 背景信息` | 角色扮演链 → 你是谁 → 背景信息 | 生活底子（通勤/大地色穿搭/旧包换包由头） | 旧包钩子被反复念叨（C1 亲戚） |
| `# 对话指导`（变量注入位）| 角色扮演链 → 对话指导 → 性子/产品变量 | `{roleplay_personality}` / `{roleplay_product}` 两个注入占位 | 性子没提权→被正文通用倾向淹没（C6） |
| `# 对话指导` → `## 沟通原则` | 角色扮演链 → 对话指导 → 沟通原则 | 性子是总开关、优先级、铁律封顶 | 提权辖域没钉死 |
| `# 对话指导` → `## 说话的味儿` | 角色扮演链 → 对话指导 → 说话的味儿 | 语感（口语/带语气/带生活/有来有往） | 逐字示范句被当台词复读（调优铁律2） |
| `# 对话指导` → `## 异议抛出指导` | 角色扮演链 → 对话指导 → 异议抛出指导 | 一来一回别查户口、做过的别重来、问过的别再问 | 同担忧换皮重抛（C5） |
| `# 对话指导` → `## 旁白机制` | 角色扮演链 → 对话指导 → 旁白机制 | 括号演动作+点明在看哪只包、克制、不写心理 | 旁白过载/未完成态/动作不算已发生（C2） |
| `# 你这趟的心路` | 角色扮演链 → 心路 → ①…⑤ | 五阶段地图（进店→需求→上手→掂量→临门）+ 只进不退 + 内生驱动 | 阶段写死问题清单→4性格趋同（C6）；缺收尾信号（C7） |
| `# ★ 铁律` | 角色扮演链 → ★铁律 → 第N条 | 最高优先级硬约束（认历史/没接住不清零/一次一个意思/只说顾客话/产品事实边界/听岔不纠正/别写文档/旧包最多一次/结束机制） | 见 C1/C4/C5/C7 各落点 |

**定位一个落点就用上表的"业务侧定位说法"**，如：【角色扮演链 → ★铁律 → 第5条·产品事实边界】，别只写"改铁律5"。

---

## 第二部分：随机池变量契约（受保护 · 改前问用户）

随机池 SSOT 按场景归属：场景1＝`场景1_质感自用Elena/随机机制/最新随机池内容.md`，场景2＝`场景2_奥莱私域轻奢Bella/随机机制/最新随机池内容.md`（**受保护**）。字段与后端代码 `NstrRoleplayCard` 对齐：`{name, content, enabled}`。

| 业务侧名称 | 注入占位 | config_key | 取值约束 |
|---|---|---|---|
| 性格池（4 张性格卡） | `${roleplay_personality}`（变量名以代码为准，**非 persona**） | `nstr.roleplay.personality-pool` | 只写"这一局的性子基调"（脾气深浅/话多话少/热络防备/最先在意什么），不重复画像、不写流程指令 |
| 产品池（6 张产品卡） | `${roleplay_product}` | `nstr.roleplay.product-pool` | 只写两样：①Elena 眼里这只包的外观口语 ②末尾一个〔本局对应款〕锚点。**产品事实（皮质/五金/精确尺寸/容量/价位）一律不写进池**（守 ADR 0003 单一来源，被问去查知识库） |

- **变量名契约是 A 桶硬规则**（`scripts/verify-local.sh` 会校验 `roleplay_personality` / `roleplay_product` 存在）——改名会与后端 `NstrRoleplayCard` 脱节，禁止擅改。
- **占位符格式注意**：当前工作文件 `最新使用提示词.md` 用单花括号 `{roleplay_personality}`；契约文档/旧 v9 草案用 `${roleplay_personality}`。**实际注入格式以后端组装代码为准**——改提示词时保留与后端一致的那种，拿不准就标"占位符格式待与后端核对"，别擅自改格式导致注入失败。
- **性格卡 ↔ 提示词两层咬合**（治 C6）：提示词侧交还"最先在意/话量/冷暖/快慢"控制权，性格卡侧给差异化锚点（A 抠耐用值不值 / B 咬别家凭啥这价 / C 只淡看第一眼颜色感觉 / D 先盯好不好看配不配）。诊断"性格穿不透"必须两层一起看。

---

## 第三部分：本地业务接口试跑（模式三 · coach 推荐）

coach 有本地业务系统，可直接调真实接口跑出最真实的 AI 顾客输出（比自扮演可信）。接口全文见 `陪练场景搭建/公共_跨场景复用/本地场景测试接口说明.md`，要点：

- **两个服务**：`confiDomainUrl=http://127.0.0.1:8080`（配置/记录侧）、`aiDomainUrl=http://127.0.0.1:80`（AI 调用侧）。当前调试场景业务系统 id＝**497**。
- **一轮完整对话的接口链**：
  1. **创建陪练记录** `POST {confiDomainUrl}/welearning/api/nstr/mobile/data/begin` → 返回 `data.id` = 本次 recordId。
  2. **SA 输入** `POST {confiDomainUrl}/welearning/api/nstr/mobile/data/recordInput`（带 `recordId`、`userInput`、递增的 `loopIndex`）→ 返回 `data.id` = 本轮 SA 输入详情 id（bindDetailId，下一步要用）。
  3. **发起 AI 顾客回答** `POST {aiDomainUrl}/ailearning/nstr/call/openStream`（带 `nstrResultId`=recordId、`bindDetailId`、`userInput`）→ 返回 `data` = serialId。
  4. **拉取 AI 回答** `GET {aiDomainUrl}/ailearning/nstr/call/sse?serialId=...`（SSE 流）。
- **取本局抽到的性格/产品**：`GET {aiDomainUrl}/ailearning/nstr/tool/getRoleRandomData?recordId=...` → 返回 `roleplay_personality` / `roleplay_product` 的实际注入值。**诊断/测试前必拉**——知道这局是 A 理性还是 C 冷淡，才能判性格层有没有穿透（C6）。
- **查/改提示词**（用户手动灌上线用）：
  - 查 `POST {confiDomainUrl}/welearning/api/nstr/tool/prompt/query`（`type: "bot_display"` = 角色扮演链提示词类型）。
  - 改 `POST {confiDomainUrl}/welearning/api/nstr/tool/prompt/update`（`prompt` = 新提示词全文，`remark` ≤200 字记本次基于什么调整）。
- **试跑建议**：同一性格/产品多跑 2–3 次看稳定性（不追影子）；跑前 dump `getRoleRandomData` 记下这局抽的卡，回归时能复盘"这局是哪种性子犯的坑"。
