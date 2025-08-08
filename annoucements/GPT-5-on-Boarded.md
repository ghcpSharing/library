
# GPT‑5 编码优势与在 GitHub Copilot 中的 premium request 说明

## 为什么在编码场景选择 GPT‑5
- 更长上下文与更大输出
  - 上下文窗口约 400K tokens，最大输出约 128K tokens，适合大型代码库、多文件重构与长对话调试。
  - 参考：OpenAI 模型文档与对比页（含上下文与输出上限）。
- 代码基准表现强
  - SWE‑bench Verified ≈ 74.9%（启用推理/思维模式时）。
  - Aider Polyglot ≈ 88%（启用推理/思维模式时，多语言代码编辑更稳）。
  - 适合复杂前端生成、跨仓库调试与大范围重构。
  - 参考：OpenAI 发布文与第三方评测汇总。
- 更低幻觉与更强可靠性
  - 在多项评测中显示更低错误/幻觉率与更稳定的长链路任务执行（尤其是启用“思维/推理”模式时）。
- 推理与工具协同
  - “思维/推理（thinking/chain‑of‑thought）”显著提升修复与重构任务成功率；与代码执行/检索等工具配合更好。

## 在 GitHub Copilot 中属于 premium request（计费与配额）
- 核心概念
  - “一次 premium request 消耗”＝“功能的基础请求次数”×“模型倍率（Model Multiplier）”。
  - 例：Copilot Chat 每次用户提示=1 次基础请求；Copilot Coding Agent 每个会话=1 次基础请求；Copilot Code Review 每次机器人发评论=1 次基础请求；Agent Mode/Extensions/Spaces 等同理按“每次提示=1”计。
  - 不同模型有不同倍率；倍率随时间更新，以 GitHub Docs 实时表为准。
- 计划与额度
  - 免费计划（Copilot Free）：每月最多 2,000 次代码补全；最多 50 次 premium requests。所有聊天都算 premium。
  - 付费计划（Pro/Pro+/Business/Enterprise 等）：代码补全与聊天使用“包含模型”（如 GPT‑4.1、GPT‑4o）不消耗 premium；但使用前沿/高算力模型（如 GPT‑5、Claude、Gemini 某些版本）按模型倍率计入 premium request 月度额度。
  - 月度额度在每月 UTC 00:00:00 的 1 号重置；未用完不会结转。
  - 超量计费：默认预算为 0，超出会被拒绝；若设置预算，超额 premium request 约 $0.04/次计费（以当月文档为准）。
- 模型倍率（消费系数）
  - 每个非“包含模型”都有一个倍率系数（越高越贵）。例如官方示例中：Claude Opus 4 在 Chat 中一次交互按 10× 计入额度；包含模型（如 GPT‑4.1、GPT‑4o）在付费计划下为 0×（不消耗 premium）。
  - GPT‑5 作为前沿模型，在 Copilot 中会计入 premium request，具体倍率以 GitHub Docs 实时表与 IDE 内显示为准（可能变动）。
- 监控与治理
  - VS Code 状态栏的 Copilot 图标可查看当前 premium request 使用进度与重置时间。
  - GitHub.com > Your Copilot > Usage 可查看并导出 45 天内的使用报告。
  - 企业/组织可为成员设置预算、查看报表、选择计费实体（多人多许可证时需在“Usage billed to”选择）。

## 在 VS Code 中启用并使用（开启组织策略后重新登录即可）
- 管理员（组织/企业）
  1. GitHub.com > 组织/企业 Settings > Copilot：开启 premium requests，允许使用目标前沿模型（如 GPT‑5），并设置预算策略与超量策略。
  2. 如多人多许可证，明确组织的计费实体，避免因未选择而被拒绝请求。
- 开发者（VS Code）
  1. 在管理员开启策略后，于 VS Code 中“注销并重新登录”GitHub 账户以刷新授权（命令面板可执行“GitHub: Sign out / Sign in”或重载窗口）。
  2. 打开 Copilot 侧边栏/状态栏，确认可选模型列表中出现 GPT‑5，并在模型选择器中切换到 GPT‑5。
  3. 点击状态栏 Copilot 图标查看“Premium requests”用量进度；必要时在 GitHub.com 的“Your Copilot > Usage”核对额度与重置时间。

## 快速选型建议
- 长上下文/长输出、多文件重构、大仓库调试：优先 GPT‑5。
- 日常聊天/轻量补全：使用包含模型（如 GPT‑4.1/GPT‑4o）不消耗 premium。
- 强编码代理与高成功率修复：在关键链路使用 GPT‑5；其它步骤用包含模型降本。
- 企业治理：为关键团队配置更高预算/更高计划，启用报表与超量告警。

## 参考链接
- OpenAI（GPT‑5 模型、上下文与基准）
  - 模型与对比（含上下文/输出上限与定价）：https://platform.openai.com/docs/models/gpt-5 https://platform.openai.com/docs/models/compare https://platform.openai.com/docs/pricing
  - 发布文（编码基准）：https://openai.com/index/introducing-gpt-5/ https://openai.com/index/introducing-gpt-5-for-developers/
- 第三方评测（佐证 GPT‑5 编码分数与上下文）  
  - Vellum 汇总（SWE‑bench≈74.9%、Aider Polyglot≈88%、400K/128K）：https://www.vellum.ai/blog/gpt-5-benchmarks
- GitHub Copilot（premium request、倍率与使用/治理）
  - 请求与计费概念（含模型倍率、超量计费与计划差异）：https://docs.github.com/copilot/concepts/copilot-billing/understanding-and-managing-requests-in-copilot
  - 使用监控与报表（VS Code 内查看、GitHub.com 报表导出）：https://docs.github.com/copilot/how-tos/monitoring-your-copilot-usage-and-entitlements
  - 组织/企业预算与额度管理入口（索引）：https://docs.github.com/copilot/how-tos/premium-requests

提示
- 模型倍率与“包含模型”列表会随时间调整；以 GitHub Docs 与 VS Code 内显示为准。
- 超量默认被拒绝；需明确预算后才会按 $/request 计费。