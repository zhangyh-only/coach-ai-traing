# 本项目编码规范

> 这里是本项目规范的**权威全文**，与代码同仓、随项目演进。
> 全局 hook `inject-conventions.sh` 会在编码任务开始时把本目录所有 `.md` 注入 AI 上下文。
> 规范一行都不缩——靠"生成时注入全文"让 AI 守，不靠缩成摘要。

## 三桶分流：每条规则按"靠什么强制"归类

写规范时，给每条规则想清楚它属于哪桶，强制方式不同：

| 桶 | 规则特征 | 强制方式 |
|---|---|---|
| A 机器可判定 | 命名、目录归属、依赖方向、必须有注释、禁用 import、禁魔法值 | 编译成**检查器**（行级：Checkstyle/ESLint/ruff…；架构：ArchUnit/dependency-cruiser…），由 `scripts/lint-one.sh` + CI 自动拦 |
| B 需判断、但每次都相关 | "注释要有信息量""按职责选后缀""归属看调用面" | 写进本目录全文，**生成时注入**让 AI 落地 |
| C 详细参照/决策背景 | 完整表格、示例、为什么这么定 | 留作全文参照 + L4 review 的对照基准 |

> A 桶是"硬保证"，B 桶是"生成时知道"，C 桶是"查得到 + 收尾兜底"。三者叠加，不互相替代。

## 文件组织（按需增减）
- `code.md` —— 编码约定：命名、分层职责、注释、错误码、代码风格…
- `structure.md` —— 结构约定：模块放置、包结构、归属判断…
- （可加 `api.md`、`<domain>.md` 等）

## 怎么落地 A 桶（机器可判）
1. 在 `code.md`/`structure.md` 里把规则写清楚（人读 + review 用）。
2. 把其中机器可判的子集，配成本语言的检查器规则（如 `checkstyle.xml` / `.eslintrc` / `ruff.toml`），并在项目 `scripts/lint-one.sh` 里接好。
3. 架构/依赖类规则写成架构测试（Java: ArchUnit；JS: dependency-cruiser…），纳入 `mvn test` / CI。
4. 在 CI 设为 required check —— 不通过不许合并（与 AI 工具无关的最终闸门）。
