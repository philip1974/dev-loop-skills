# Wiki Red-Team Checklist

来源：`wiki/synthesis/dev-loop-design.md` 议题 C.4 + C.5

`dl-red-team` 在 **wiki 或 mixed** 项目类型下，必须强制 codex 在红队答案中检查以下 14 项。code-only 项目不强制（但 C5/C12/C14 仍建议）。

## 14 项强制检查

| ID | 检查项 |
|---|---|
| C1 | `raw/` 是否被明确标为只读，plan 是否存在修改/重命名/删除 `raw/` 的风险 |
| C2 | 每个事实性陈述是否有 source card 支撑，未支撑内容是否会标 `[unverified]` |
| C3 | 是否需要新建或更新 `wiki/sources/`，source card 的 `wiki_pages` 是否同步维护 |
| C4 | 是否禁止 synthesis 直接引用 raw 文件，而是通过 source card 引用 |
| C5 | 受影响页面类型是否正确（concept / entity / synthesis / question / source / index / log） |
| C6 | frontmatter 是否完整（type / status / created / updated / sources 符合项目约定） |
| C7 | wikilink 是否可解析；新增页面 slug 是否稳定、小写 ASCII、连字符分隔 |
| C8 | `wiki/index.md` 是否需要更新，导航是否会遗漏新页面 |
| C9 | `wiki/log.md` 是否只追加，是否记录本次摄取/查询写回/lint |
| C10 | 是否会静默删除冲突陈述；若有冲突，是否计划标注 `[conflict]` 并解释 |
| C11 | 是否保留用户已有内容，避免大范围无说明重写 |
| C12 | 是否区分"聊天回答"和"长期 wiki 写回"，避免把临时判断写成知识库事实 |
| C13 | 是否需要 lint 或 targeted link/source check；verify 阶段如何验证 |
| C14 | 对 trivial/micro 任务是否过度流程化，是否可降级 |

## 7 个易忽略的坑（codex 提示，建议红队 prompt 末尾附）

1. **source card 是事实入口不是装饰** — 没有源卡的 synthesis 很快变成不可审计散文
2. **index/log 经常被漏改** — 页面存在但不可发现 / 操作发生但不可追踪
3. **不仅问"能不能做"，还要问"做完后未来维护者能不能理解为什么这么做"**
4. **删除重复内容很危险** — 重复可能代表来源冲突或不同抽象层级，不能静默合并
5. **责任空洞**：Claude 以为 codex 会补引用，codex 以为 plan 已经确认来源——**红队 prompt 必须显式追问"每个拟写事实来自哪里"**
6. **verify 要检查知识结构而非文件 diff**：新增 source 是否被 index 发现 / source card 是否反链到页面 / 页面是否有入站链接
7. **micro 任务可以轻量，但 safeguards 不能省**：尤其"不碰 raw、不伪造引用、不静默覆盖用户内容"
