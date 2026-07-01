# Coach 提示词结构 + 内部材料映射 + 接口试跑

诊断的事实基础。三部分：①角色扮演链提示词的分块结构（落点定位用）②内部材料/随机池契约（模板替换位、字段、状态账本）③本地业务接口试跑流程。

> 通用版那张"业务 UI 名称↔schema 字段↔Freemarker 注入点"的大表（botAction/maxRounds/phaseProblems/character_profile…）是**百炼 Agent 2.0** 的配置项。**coach 角色扮演链已切回直调模型、不走 Agent 应用**，那套配置项**不适用**——coach 的"阶段/异议/画像"全部写在提示词正文里，不是平台配置。故本文件按 coach 实际重写。
>
> 最新口径：后端按模板替换位组装最终完整 prompt 后直调模型。模板里可以有 `{rolePlayPersonality}` / `{rolePlayProduct}` / `{rolePlayState}`，但模型可见正文必须写成"本局性子 / 看上的包 / 已聊历史 / 内部材料"，不要向模型解释变量、占位符、程序注入。

---

## 第一部分：角色扮演链提示词分块结构（落点定位）

各场景正式 prompt 以场景目录里的 `最新使用提示词.md` / `agent最新使用提示词.md` 为准，受保护与否按仓内 guard。当前推荐结构（Bella v0.3 后沉淀）：

| 区块 | 业务侧定位说法 | 装什么 | 常见落点坑 |
|---|---|---|---|
| `# 重要前提` | 角色扮演链 → 重要前提 → 内部材料 | 本局性子、看上的包、已聊历史。模板可放 `{rolePlay*}`，解释必须是"内部材料" | 把工程变量说给模型听；空历史时读出占位 |
| `# 一、你是谁` | 角色扮演链 → 你是谁 → 稳定画像 | 场景固定画像、消费动机、生活底子、外部视角顾客 | 画像替顾客提前下结论；正价/奥莱画像混用 |
| `# 二、这一局的你` | 角色扮演链 → 本局行为卡 | 性格行为卡如何控制话量、先问点、证据阈值、追问策略、冷热推进 | 性格卡被正文压平（C6） |
| `# 三、你怎么说话` | 角色扮演链 → 说话/旁白 | 口语短、一次一事；旁白只写可见动作+看哪款、完成态、少量关键时刻 | 旁白过载/未完成态/心理泄漏（C2） |
| `# 四、几条守住的线` → 认历史 | 角色扮演链 → 状态账本 | 每轮第一行固定 `<?STATE 关切=...；动作=...；表态=...>`；只记新增 | 状态断档、问过/做过又重来（C1） |
| `# 四、几条守住的线` → 同类担忧 | 角色扮演链 → 顾虑消耗 | 按底层意思合并正品/渠道、价格、搭配、退换、容量等；最多追一两轮 | 同担忧换皮重抛（C5） |
| `# 四、几条守住的线` → 产品边界 | 角色扮演链 → 产品事实边界 | 顾客只知道看得见摸得着；不查库、不报参数、不替导购讲卖点 | 顾客越界成专家（C3/C4） |
| `# 五、什么时候结束` | 角色扮演链 → 结束机制 | 两段式收尾；`<?END_CHAT>` 只跟最后自然告别句；收尾轮仍先写 `<?STATE ...>` | END_CHAT 早出/不出；误伤 STATE（C7） |

**定位一个落点就用上表的"业务侧定位说法"**，如：【角色扮演链 → ★铁律 → 第5条·产品事实边界】，别只写"改铁律5"。

---

## 第二部分：内部材料与随机池契约（受保护 · 改前问用户）

随机池 SSOT＝`公共_跨场景复用/随机机制/最新随机池内容.md`（**受保护**）。字段与后端代码 `NstrRoleplayCard` 对齐：`{name, content, enabled}`。

| 业务侧名称 | 模板替换位 | 来源/配置 | 取值约束 |
|---|---|---|---|
| 本局性子/行为卡 | `{rolePlayPersonality}` | 场景对应 personality-pool | 只写"这一局怎么反应"，不重复画像、不写具体台词、不写流程脚本 |
| 本局看上的包 | `{rolePlayProduct}` | product-pool / 动态产品选择 | 只当外观锚点和内部对应款参考；不要让顾客嘴上报型号、皮料、尺寸、价位；色名必须沿用产品卡或降到同一上位色，不能改成另一个近似营销色名 |
| 已聊历史 | `{rolePlayState}` | 后端从历史 `<?STATE ...>` 抽取 | 内部只读账本，用来判断关切/动作/表态是否已发生；提示词必须消费但不能说出口 |

- **命名面以当前后端组装代码为准**：最新口径统一 camelCase `rolePlay*`。如果旧文档里看到 `${roleplay_personality}` / `${roleplay_product}`，先当历史口径或旧 SSOT guard，别直接复制进新场景。
- **模型可见正文不讲"变量"**：模板替换位只存在于搭建层；正文解释用"内部材料/已聊历史"，不要让顾客读出 `{rolePlayState}` 或解释"程序给我的变量"。
- **产品色名锚定**：产品卡的颜色是本局视觉锚点。模型可见正文不要写死某个具体色名示例，也不要逐字列"禁止说的错色名"；用类别规则约束"沿用原色名，最多降到同一上位色，不另起近似色名"。
- **性格卡 ↔ 提示词两层咬合**（治 C6）：提示词侧交还"最先在意/话量/冷暖/快慢/证据阈值/追问硬度"控制权，性格卡侧给差异化锚点。诊断"性格穿不透"必须两层一起看。
- **Bella v0.3 行为卡结构**（借鉴 agency-agents 后固定）：`说话气质` / `最先关切` / `证据阈值` / `追问策略` / `被打动信号` / `被推开信号`。不要扩成几十上百张角色；Coach 更需要少量高差异、可回归的性格卡。每张卡必须写出追问后的出口动作，避免性格差异被模型放大成连续盘问。

---

## 第三部分：本地业务接口试跑（模式三 · coach 推荐）

coach 有本地业务系统，可直接调真实接口跑出最真实的 AI 顾客输出（比自扮演可信）。接口全文见 `陪练场景搭建/公共_跨场景复用/本地场景测试接口说明.md`，要点：

- **两个服务**：`confiDomainUrl=http://127.0.0.1:8080`（配置/记录侧）、`aiDomainUrl=http://127.0.0.1:80`（AI 调用侧）。当前调试场景业务系统 id＝**497**。
- **一轮完整对话的接口链**：
  1. **创建陪练记录** `POST {confiDomainUrl}/welearning/api/nstr/mobile/data/begin` → 返回 `data.id` = 本次 recordId。
  2. **SA 输入** `POST {confiDomainUrl}/welearning/api/nstr/mobile/data/recordInput`（带 `recordId`、`userInput`、递增的 `loopIndex`）→ 返回 `data.id` = 本轮 SA 输入详情 id（bindDetailId，下一步要用）。
  3. **发起 AI 顾客回答** `POST {aiDomainUrl}/ailearning/nstr/call/openStream`（带 `nstrResultId`=recordId、`bindDetailId`、`userInput`）→ 返回 `data` = serialId。
  4. **拉取 AI 回答** `GET {aiDomainUrl}/ailearning/nstr/call/sse?serialId=...`（SSE 流）。
- **取本局抽到的性格/产品**：`GET {aiDomainUrl}/ailearning/nstr/tool/getRoleRandomData?recordId=...` → 返回本局性格/产品实际内容（字段名以当前接口为准，常见为 `rolePlayPersonality` / `rolePlayProduct` 或旧口径 `roleplay_personality` / `roleplay_product`）。**诊断/测试前必拉**——知道这局是 A 理性还是 C 冷淡，才能判性格层有没有穿透（C6）。
- **查/改提示词**（用户手动灌上线用）：
  - 查 `POST {confiDomainUrl}/welearning/api/nstr/tool/prompt/query`（`type: "bot_display"` = 角色扮演链提示词类型）。
  - 改 `POST {confiDomainUrl}/welearning/api/nstr/tool/prompt/update`（`prompt` = 新提示词全文，`remark` ≤200 字记本次基于什么调整）。
- **试跑建议**：同一性格/产品多跑 2–3 次看稳定性（不追影子）；跑前 dump `getRoleRandomData` 记下这局抽的卡，回归时能复盘"这局是哪种性子犯的坑"。
