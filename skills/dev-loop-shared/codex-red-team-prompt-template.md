# Codex Red-Team Prompt Template

来源：`wiki/synthesis/dev-loop-design.md` 议题 A.5 / C.4 / D.2 / G

`/dl-red-team` 在喂 plan 给 codex 时使用此模板。模板占位符 `{{XXX}}` 由 skill 替换。

---

```
codex，dev-loop red-team 任务。

## 铁律（必须遵守）
1. 不读取或修改任何 dev-loop 草稿/设计文件（包括 wiki/synthesis/dev-loop-design.md、本 topic 目录下的 plan-vN.md 之外的文件）
2. 不写任何文件
3. 只在 chat 中输出
4. 结束时**另起一行**打印：###CODEX-DONE###

## 项目上下文
- 仓库：{{PROJECT_ROOT}}
- 项目类型：{{PROJECT_TYPE}}     # code / wiki / mixed
- 任务复杂度：{{COMPLEXITY}}      # micro / standard / major
- topic_id：{{TOPIC_ID}}
- 项目铁律摘要（来自 CLAUDE.md / AGENTS.md）：
{{PROJECT_RULES_DIGEST}}

## 你要红的 plan
（以下是 /dl-plan 阶段产出的 plan-v{{N}}.md 全文。**仅审查这一份**，不要读其他 dev-loop 文件。）

---
{{PLAN_CONTENT}}
---

## 你的任务

按以下结构独立批判（不要附和 Claude，发现问题就直说）：

### Verdict
- Decision: BLOCK | REVISE | PASS
- One-line reason: ...

### P0 Blockers（必须改才能 execute）
- [P0-1] 问题：
  - 为什么阻塞：
  - 建议修正：
  - 影响范围：

### P1 Major Risks（建议改）
- [P1-1] 问题：
  - 风险：
  - 建议修正：

### P2 Improvements
- [P2-1] ...

### Answers To Required Questions
（plan 末尾"必答问题清单"逐条回答）
- Q1: ...
- Q2: ...

### NEED-INFO（如有）
- [NEED-INFO-1] 缺什么：
  - 为什么影响判断：
  - 谁能提供：

### Integration Notes
- Claude integrate 时应保留：
- Claude integrate 时应改写：
- 不建议进入 execute 的条件：

{{WIKI_CHECKLIST_BLOCK}}

###CODEX-DONE###
```

## `{{WIKI_CHECKLIST_BLOCK}}` 注入规则

- `project_type ∈ {wiki, mixed}` 时注入下面整段
- `project_type = code` 时**不注入**（但 C5/C12/C14 项可保留为附加 prompt）

```
### Wiki-Specific Forced Checks（14 项 + 7 坑追问）

请逐项给出 PASS / FAIL / N/A + 一句理由：

{{WIKI_CHECKLIST_14_ITEMS}}

并在答案中显式追问：**"每个拟写事实来自哪里？"**（防 Claude/Codex 责任空洞——任一方都假设对方会补引用）。
```

## `{{PROJECT_RULES_DIGEST}}` 生成规则

- 读取 `{{PROJECT_ROOT}}/CLAUDE.md`、`{{PROJECT_ROOT}}/AGENTS.md`（若存在）
- 抽前 50 行 + 任何带"不要 / 禁止 / 必须 / 铁律 / safety / safeguard"关键字的段落
- 若都不存在，注入：`(无 CLAUDE.md / AGENTS.md，按通用约定处理)`

## 复杂度档位调整

- `complexity = micro`：**跳过红队**——不调用本模板
- `complexity = standard`：默认模板
- `complexity = major`：在 Verdict 段后注入 "逐维审查" 提示，强制 codex 按 REASONS 7 维度（Requirements/Entities/Approach/Scope/Operations/Norms/Safeguards + Unknowns）各给一条评论

## 完成判定

`/dl-red-team` 等待 codex 完成的策略（议题 A）：
- 270s × 最多 3 轮 ScheduleWakeup（共 ~13.5 min 上限）
- 唯一成功信号：单独一行 `###CODEX-DONE###`
- 缺 sentinel 但有看似完整输出 → 标 `manual_override: true` 需人工确认
- 全程 timeout → 标 `red-team status: incomplete`，允许 1 次重发，再失败走 degraded path（Claude 自审 + 标风险）
