# REASONS Canvas — Adopted Takeaways

来源：`wiki/synthesis/dev-loop-design.md` 议题 G

REASONS（Requirements / Entities / Approach / Scope / Operations / Norms / Safeguards）来自外部 slide deck，**当 inspiration 不当 schema**。本 dev-loop 不强制 7 维度全字段命名，也不严格用 R/E/A/S/O/N/S 字母——只采纳以下 5 条 takeaway。

## 5 条采纳的 takeaway

1. **A/O 不在 /dl-req 阶段填**
   - Approach（策略）和 Operations（实现步骤、方法签名）属于设计活，不是需求
   - /dl-req 可留 `TBD by /dl-plan`，但必须说明"为什么暂留 + 哪些约束限制后续方案"
   - 反例：req.md 写"用 Redis 缓存"——这是 plan 的活

2. **Scope 和 Safeguards 必须明确区分**
   - Scope = 影响范围（哪些 module / 哪些 wiki 页 / 改哪些目录）
   - Safeguards = 不可碰的边界（性能红线 / 安全约束 / 禁止操作 / raw/ 只读）
   - 不要混着写"约束"——会丢失 Safeguards 的强制性

3. **必须有显式 Unknowns / Open Questions 字段**
   - REASONS 原表没有，但 dev-loop 必须加
   - 否则 TBD 散落在各处，红队找不到全
   - 字段名建议 `unknowns:` 或 `open_questions:`

4. **整体当版本化 Canvas 看**
   - REASONS 不是 /dl-req 的一次性 form
   - 是贯穿 req → plan → red-team → integrate → execute → verify 的状态对象
   - 配合议题 B.3 的 plan-vN.md 多文件机制——每个版本是 Canvas 的一次快照

5. **verify 阶段不只验 Requirements，也验 Norms 和 Safeguards**
   - 很多失败不是功能没做，而是做的过程中碰了不该碰的边界
   - /dl-verify 必须显式检查 N + S，不止 R

## 三档复杂度（micro / standard / major）

`/dl-req` 启动时必须判断任务档位，影响后续 skill 的繁简度：

| 档位 | 触发场景 | /dl-req 填什么 | /dl-red-team | /dl-verify |
|---|---|---|---|---|
| **micro** | typo / 单 wikilink / 格式小修 | 只填 Requirements + Scope + Safeguards 一句话 | **跳过** | targeted check（不跑全 lint） |
| **standard** | 普通改动 | 完整字段，A/O 可简洁，允许 `N/A: <理由>` | 通用红队 | 标准 verify |
| **major** | 跨模块 / 改规范 / 影响数据-安全-性能 / 写长期 wiki 结论 | 完整 + Unknowns 显式 | **逐维审查**，红队 prompt 加严 | 完整 verify + 知识结构检查 |

**金句**："REASONS 的价值是降低遗漏，不是把 2 分钟修复变成 20 分钟仪式。"

## 不采纳

- 不强制 REASONS 7 维度字段命名
- 不严格用 R/E/A/S/O/N/S 字母作 section heading（用语义全名 Requirements/Entities/Approach/Scope/Operations/Norms/Safeguards）
- 不给 REASONS 框架本身建 source-card（外部参考非引用）
