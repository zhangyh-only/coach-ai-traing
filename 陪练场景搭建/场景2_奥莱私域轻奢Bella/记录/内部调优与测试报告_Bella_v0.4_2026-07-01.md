# 内部调优与测试报告：Bella 奥莱角色扮演链 v0.4

日期：2026-07-01

场景：场景2「奥莱私域轻奢 Bella」

接口配置：

- baseId=507
- botDisplayConfigId=764
- flowId=413
- get-input actionId=2431
- bot-answer actionId=2432

## 背景

奥莱场景测试中连续暴露出几类角色扮演问题：

- 正品 / 正价 / 专柜差异反复问，已经得到官方渠道、小票、售后说明后仍换说法追问。
- 价格过度纠缠，导购已经给到到手价和底价边界后仍追“到底多少 / 还能不能便宜”。
- 材质、清洁、护理服务被拆成多轮问题，问过“是不是麂皮 / 难不难清洁 / 有没有护理服务”后仍重新打开。
- 产品锚点偶发漂移，例如暖棕被说成焦糖色。
- 旁白偶发写心理活动，或 `<?STATE>` 首轮缺失。
- 收尾时“再想想”送客后偶发漏 `<?END_CHAT>`。

## 调整范围

### 提示词

文件：`最新使用提示词.md`

关键调整：

- 把提示词结构稳定为“内部材料 / 人设 / 性格行为卡解释 / 说话与旁白 / 状态账本 / 同类关切消耗 / 产品事实边界 / 收尾机制”。
- 将 `<?STATE>` 固定为 `关切 / 动作 / 表态` 三字段，并在第一屏前置硬要求：每轮第一行都必须写，第一轮也不能省。
- 将同类关切按底层意思归并：正品/渠道安心、划算价格、搭配闲置、打理耐用、版型塌变形、容量、退换兜底。
- 明确 `打理耐用` 包含材质名、绒面/麂皮、清洁难度、护理服务、刮花磨花、保养等，导购给过任一实在说法后不再拆成新问题。
- 产品锚点增加颜色约束：口头颜色必须沿用本局产品卡或同一上位色，不能改成相近但不同的色名。
- 旁白规则收紧：括号只允许导购看得见的动作、视线和拿包动作；不能写“心里、盘算、觉得、担心、放心”等内心词。
- 收尾规则补强：成交、再想想、不买都走两段式；Bella 先表态，导购送客后，下一句自然告别并加 `<?END_CHAT>`。

线上灌入记录：

- `Bella v0.4 old-topic redelivery guard`
- `Bella v0.4 visible-action aside guard`
- `Bella v0.4 strict visible-action aside guard`
- `Bella v0.4 strict state and aside guard`
- `Bella v0.4 strict end-chat guard`

当前线上使用最后一版：`Bella v0.4 strict end-chat guard`。

### 随机池

文件：`随机机制/最新随机池内容.md`

关键调整：

- 参考 `agency-agents` 的结构化角色卡思路，将性格卡从单句性格描述升级为行为卡。
- 每张卡固定包含：说话气质、最先关切、证据阈值、追问策略、被打动信号、被推开信号。
- 四张卡分别收敛边界：
  - A-精算型：价格先问当前价，给到到手价或底价边界后停止追价；打理只在未聊过时问一次。
  - B-比价型：奥莱、正价、网上、官方渠道合并成一个选择理由，不轮流拆问。
  - C-怕踩坑型：每局只先冒一个安全感顾虑，不把正品、退换、打理、搭配展开成清单。
  - D-心动型：先围绕上身和搭配推进，临门前只补一个真实确认，不把风险补成清单。

507 的 `rolePlayPersonality` 已替换为新卡；产品池沿用当前 `rolePlayProduct`，但后续提示词对产品锚点做了更强约束。

### 后端

后端仓：`/Users/zhangyh/code/branches/ailearning_0630_fix`

关键类：

- `NstrBotDisplayCallServiceImpl`
- `NstrRoleplayCustomVariableHandler`
- `NstrRoleplayPromptTraceService`
- `NstrToolController`

调整：

- 增加最终 prompt trace：模型调用前把已替换的最终 prompt 按 `recordId + loopIndex` 存 Redis，保留 3 天。
- 新增查询接口：`GET /ailearning/nstr/tool/getRoleplayPromptTrace?recordId=...&companyCode=...`。
- `rolePlayState` 历史账本从简单去重升级为结构化解析 `关切 / 动作 / 表态`。
- 后端追加“已聊同类关切提醒”，按底层意思归并正品/渠道、划算价格、搭配闲置、打理耐用、版型塌变形、容量、退换兜底。
- 销售输入也参与“同类关切是否已聊过”的扫描；但动作和表态仍只从 Bella 自己的 `<?STATE>` 抽取，避免把导购话术误写成顾客状态。

后端单测：

```bash
JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk-1.8.jdk/Contents/Home PATH=/Library/Java/JavaVirtualMachines/jdk-1.8.jdk/Contents/Home/bin:$PATH mvn -Dtest=NstrRoleplayPromptTraceServiceTest,NstrRoleplayCustomVariableHandlerTest test
```

结果：5 tests / 0 failures / 0 errors。

## 测试覆盖

### 1. 主批跑

报告文件：`记录/接口测试输出/batch_regression_20260701_183453.json`

结果：

- 9 局有效，0 局污染。
- 覆盖 A-精算型、B-比价型、C-怕踩坑型、D-心动型四张性格卡。
- 覆盖 Tabby 20、Tabby Shoulder Bag 20/26、Chain Tabby 26、麂皮 Tabby 26 等产品。
- 覆盖棕色系、浅色、麂皮/绒面。
- 9/9 最终 prompt 无未替换 `rolePlay*` 占位。
- 9/9 第 2 轮后出现正品/渠道安心、划算价格、打理耐用三类已聊提醒。
- 9/9 未出现闭合后重问正品、价格、材质/清洁/护理服务。

### 2. 旁白补跑

报告文件：`记录/接口测试输出/batch_aside_regression_20260701_184211.json`

结果：

- 4 局中 3 局有效，1 局 SSE 超时污染。
- 3/3 有效样本无心理括号。
- 3/3 有效样本无旧关切重问。
- 3/3 有效样本无 prompt 占位残留。

### 3. 状态标签冒烟

样本：

- `recordId=157522`
- `recordId=157523`

结果：

- 2/2 每一轮都有 `<?STATE>`。
- 2/2 无心理括号。
- 2/2 无旧关切重问。
- 2/2 trace 出现三类已聊提醒。

### 4. 结束机制回归

第一轮报告：`记录/接口测试输出/end_chat_regression_20260701_185507.json`

- `recordId=157524` 成交收尾通过。
- `recordId=157525` 再想想收尾失败，导购送客后 Bella 没有加 `<?END_CHAT>`。

修补后第二轮报告：`记录/接口测试输出/end_chat_regression_strict_20260701_185801.json`

- `recordId=157526` 再想想收尾通过，输出 `<?END_CHAT>`。
- `recordId=157527` 输出 `<?END_CHAT>`；但导购脚本在 Bella 表态再想想后仍用了开单话术，因此只计入结束标签机制通过，不计入成交质量样本。

当前结论：

- 最新线上 prompt 下，2/2 有效样本能走到 `<?END_CHAT>`。
- 成交型干净样本参考 `157524`；再想想型干净样本参考 `157526`。

## 当前结论

奥莱 Bella v0.4 已解决本轮高频复发问题：

- 正品/渠道安心不再换皮重问。
- 价格不再持续砍价式纠缠。
- 材质/清洁/护理服务不再拆成多轮风险清单。
- 产品颜色锚点稳定，未再出现暖棕误说焦糖色。
- 状态账本、旁白可见动作、收尾 `<?END_CHAT>` 已经有回归证据。

## 残留风险

- SSE 偶发超时会导致客户端断开后服务端出现 `Broken pipe` 日志噪音；这属于接口稳定性/测试方式问题，不计入角色行为结论。
- 角色扮演模型仍有随机性，后续人工验收仍建议重点观察括号旁白是否只写可见动作，以及送客后是否稳定带 `<?END_CHAT>`。
- 本轮回归集中在角色扮演链；实时评估链、整体评估链不在本次范围内。
