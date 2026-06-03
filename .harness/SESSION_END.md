# Session 结束协议

## 第零步：捕获新需求与约束（所有阶段通用）

- 用户提到的新想法/反馈 → 追加到 `backlog.md` 待评估区（格式：`- [日期] [来源] 描述`）
- 发现新约束/坑 → 追加到 `backlog.md` 已知约束区（格式：`[YYYY-MM-DD] 描述 — 原因`）
- 无则跳过。

## 第一步：判断本次会话阶段

回顾本次对话内容，判断属于哪个生命周期阶段：

| 判断依据 | 阶段 |
|----------|------|
| 讨论了需求、用户故事、功能想法 | **DISCOVER** |
| 讨论了架构、方案、选型、UI 设计 | **DESIGN** |
| 规划了 Sprint、拆解任务、排优先级 | **PLAN** |
| 写了代码、实现了功能 | **BUILD** |
| 测试、验证、排查了 Bug | **VERIFY** |
| 发布了版本、打了 tag | **RELEASE** |
| 做了复盘、总结、回顾 | **RETRO** |
| 做了临时快速修复或小改动 | **FIX** |

## 第二步：按阶段执行收尾

### BUILD 阶段

1. 完成的功能 → `features.json` passes 改为 true（只能 false→true）
2. 创建 Session 摘要：`registry/sessions/YYYY-MM-DD-HHmm.md`（内容：完成了什么、未完成什么、下次从哪开始）
3. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] DONE 摘要 → sessions/文件名`
4. `git add .harness/ && git commit -m "chore: session YYYY-MM-DD HH:mm - 摘要"`

### FIX 子模式

1. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] FIX 修复内容`
2. `git add .harness/ && git commit -m "chore: session ..."`

### DISCOVER 阶段

1. 若有产出文档 → 写入 `docs/requirements/YYYY-MM-DD-[主题].md`
2. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] DISCOVER 摘要`
3. `git add .harness/ && git commit -m "chore: session YYYY-MM-DD HH:mm - 摘要"`

### DESIGN 阶段

1. 若有架构决策 → 创建 `registry/decisions/YYYY-MM-DD.md`
2. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] DECISION 摘要 → decisions/文件名`
3. `git add .harness/ && git commit -m "chore: session YYYY-MM-DD HH:mm - 摘要"`

### PLAN 阶段

1. 新功能 → 追加到 `features.json`
2. 更新 `current-sprint.md` 元数据（阶段/目标/默认阶段）
3. 有功能被取消/推迟 → 追加到 `backlog.md` "已规划/已否决/变更"区
4. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] PLAN 摘要`
5. `git add .harness/ && git commit -m "chore: session YYYY-MM-DD HH:mm - 摘要"`

### VERIFY 阶段

1. 发现 Bug → 追加到 `backlog.md` 待评估区（来源：`[VERIFY]`）
2. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] VERIFY 摘要`
3. `git add .harness/ && git commit -m "chore: session YYYY-MM-DD HH:mm - 摘要"`

### RELEASE 阶段

1. 发布说明 → `docs/releases/vX.Y.Z.md`
2. `git tag vX.Y.Z`
3. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] RELEASE vX.Y.Z`

### RETRO 阶段

1. 复盘文档 → `registry/decisions/retro-N.md`
2. 改进行动项 → 追加到 `backlog.md` 待评估区（来源：`[RETRO]`）
3. `_index.md` 最前面追加：`[YYYY-MM-DD HH:mm] RETRO 摘要`
4. `git add .harness/ && git commit -m "chore: session YYYY-MM-DD HH:mm - 摘要"`

## 最后：告知用户

本次完成了什么、未完成什么、下次建议从哪里开始。
