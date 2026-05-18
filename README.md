# dev-loop-skills

Claude Code skill 集合，包含两个相关 family：

- **dev-loop**（6 阶段）：req → plan → red-team → integrate → execute → verify。用于把一个有不确定性的开发议题，从需求确认走到带证据的验收。
- **il-loop**（4 阶段，dev-loop 的简化派生）：triage → brief → fix → verify。专门处理 GitHub issue，按 trivial / normal / heavy 路径分流。

两个 family 共享：codex 红队（red-team）由独立 codex agent 执行；Claude 是编排者与日志写入者，不在 execute 阶段直接改项目文件。

## 目录

```
skills/
  dl-req/SKILL.md        # Stage 1/6
  dl-plan/SKILL.md       # Stage 2/6
  dl-red-team/SKILL.md   # Stage 3/6  调用 codex via continuo MCP terminal
  dl-integrate/SKILL.md  # Stage 4/6
  dl-execute/SKILL.md    # Stage 5/6  派 codex 执行；最高 side-effect
  dl-verify/SKILL.md     # Stage 6/6  real-test gate；commit-side-effect

  il-triage/SKILL.md     # Stage 1/4
  il-brief/SKILL.md      # Stage 2/4  normal 路径才走，trivial 跳过
  il-fix/SKILL.md        # Stage 3/4  D3 五选一失败处理
  il-verify/SKILL.md     # Stage 4/4  三道独立 gate：push / PR / close

shared/
  codex-red-team-prompt-template.md
  project-detect.sh
  reasons-takeaways.md
  topic-metadata-template.yaml
  wiki-red-team-checklist.md

design/
  il-loop-design-v1.md
  il-loop-design-v2.md
```

## 安装

把需要的 skill 目录拷或软链到 `~/.claude/skills/`：

```sh
ln -s "$(pwd)/skills/dl-req"        ~/.claude/skills/dl-req
ln -s "$(pwd)/skills/dl-plan"       ~/.claude/skills/dl-plan
# ... 其余同理
ln -s "$(pwd)/shared"               ~/.claude/dev-loop-shared
```

## 触发约定

所有 skill 都是 **explicit-trigger-only**：只能由用户通过 `/dl-*` `/il-*` 或显式中文短语（"进入 plan 阶段"、"为 issue NN 写 brief" 等）调用，模型不得自动触发。原因写在每个 SKILL.md 的 description 字段里。

## 外部依赖

- `continuo` MCP server：red-team / execute / fix 阶段通过 continuo 的 terminal 工具驱动 codex session。
- `gh` CLI：il-loop 全程使用。
- `codex` CLI：red-team 阶段的独立批判者。
