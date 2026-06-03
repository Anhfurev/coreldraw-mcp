#!/usr/bin/env bash
# .harness/hooks/session-start.sh
# Claude Code SessionStart hook
# 返回的 stdout 会作为 additionalContext 注入到 Claude 的上下文里
# 不需要 exit code 控制（SessionStart 无法阻止启动）

HARNESS_DIR=".harness"

# 如果 .harness 目录不存在，静默退出（项目还没初始化）
[ -d "$HARNESS_DIR" ] || exit 0

# 只在 Claude Code 环境中输出（opencode/Cursor 等工具有独立机制）
[ "${CLAUDE_CODE_HOOKS:-}" = "1" ] || exit 0

# ── 注入内容开始 ──────────────────────────────────────────────
cat << 'HEADER'
╔══════════════════════════════════════════════════════╗
║          HARNESS SESSION START — 自动加载            ║
╚══════════════════════════════════════════════════════╝
HEADER

# ── 检测上次 Session 是否遗漏了 SESSION_END ──────────────────
# 判断依据：.harness/ 目录有未提交的修改（有实质工作但未提交）
if git rev-parse --git-dir >/dev/null 2>&1; then
    harness_dirty=$(git status --porcelain -- "$HARNESS_DIR" 2>/dev/null)
    if [ -n "$harness_dirty" ]; then
        echo ""
        echo "## ⚠️ 上次 Session 可能未完成 SESSION_END"
        echo ""
        echo ".harness/ 有未提交的变更："
        echo "$harness_dirty"
        echo ""
        echo "**建议先补录上次的 SESSION_END（更新 _index.md 并 git commit），再开始今天的工作。**"
        echo ""
    fi
fi

# ── 检测 product 目录是否待初始化（从旧版本升级的项目）──
if [ -f "$HARNESS_DIR/product/backlog.md" ] && \
   grep -q 'HARNESS_NEEDS_INIT' "$HARNESS_DIR/product/backlog.md" 2>/dev/null; then

cat << 'INIT_NOTICE'

## ⚠️ 紧急优先任务：Product 文件待初始化

这个项目是从旧版 harness-kit 升级的，.harness/product/ 目录刚刚创建，内容为空白模板。

**在执行正常 SESSION_START 流程之前，你必须先完成以下初始化：**

1. 读取以下文件了解项目信息：
   - README.md（如有）
   - CLAUDE.md 或 AGENTS.md
   - `git log --oneline -20`（近期提交历史）
   - 项目根目录下的主要源文件结构

2. 根据以上信息，填写 `.harness/product/backlog.md` 中的占位符：
   - "产品方向"区 → 产品定位、成功标准、不做什么
   - "已知约束与坑"区 → 架构约束和已知坑

3. 删除 backlog.md 顶部的 `<!-- HARNESS_NEEDS_INIT -->` 行

4. git commit：`chore: 初始化 product backlog`

5. 完成后，继续执行正常 SESSION_START 流程

**注意：信息不足的字段写"（暂无，待补充）"，不要留模板占位符。**

---
INIT_NOTICE

fi

echo ""
echo "## 你必须立即做的第一件事"
echo ""
echo "执行 SESSION_START 检查清单（见下方），然后向用户汇报状态，等待确认后再开始工作。"
echo "不得跳过这个步骤，不得在汇报前开始任何实质性工作。"
echo ""
echo "---"
echo ""

# ── 注入 registry 最近 5 条 ──
echo "## 最近决策索引（最新在上）"
echo ""
if [ -f "$HARNESS_DIR/registry/_index.md" ]; then
    # 跳过文件头注释，取实际条目前 5 行
    grep -v '^#\|^>\|^$\|^格式\|^类型' "$HARNESS_DIR/registry/_index.md" \
      | grep -v '^---\|^<!--' \
      | head -5
else
    echo "（registry 尚未初始化，请先运行 HARNESS_SETUP.md）"
fi

echo ""
echo "---"
echo ""

# ── 注入当前 sprint ──
echo "## 当前阶段目标"
echo ""
if [ -f "$HARNESS_DIR/state/current-sprint.md" ]; then
    head -20 "$HARNESS_DIR/state/current-sprint.md"
else
    echo "（current-sprint.md 不存在）"
fi

echo ""
echo "---"
echo ""

# ── 注入未完成功能数量 ──
echo "## 未完成功能统计"
echo ""
if [ -f "$HARNESS_DIR/state/features.json" ]; then
    total=$(python3 -c "
import json, sys
try:
    d = json.load(open('.harness/state/features.json'))
    print(len(d.get('features', [])))
except: print('?')
" 2>/dev/null)
    pending=$(python3 -c "
import json, sys
try:
    d = json.load(open('.harness/state/features.json'))
    print(sum(1 for f in d.get('features',[]) if not f.get('passes',False)))
except: print('?')
" 2>/dev/null)
    echo "共 $total 个功能，未完成 $pending 个"
    echo ""
    # 列出未完成的（最多 5 个）
    python3 -c "
import json
try:
    d = json.load(open('.harness/state/features.json'))
    pending = [f for f in d.get('features',[]) if not f.get('passes',False)]
    for i, f in enumerate(pending[:5]):
        print(f'- {f[\"id\"]}: {f[\"description\"]}')
    if len(pending) > 5:
        print(f'... 还有 {len(pending)-5} 个，见 features.json')
except Exception as e:
    print('（读取失败）')
" 2>/dev/null
else
    echo "（features.json 不存在）"
fi

echo ""
echo "---"
echo ""

# ── 注入 SESSION_START 检查清单 ──
echo "## SESSION_START 检查清单（现在执行）"
echo ""
if [ -f "$HARNESS_DIR/SESSION_START.md" ]; then
    cat "$HARNESS_DIR/SESSION_START.md"
else
    echo "（SESSION_START.md 不存在）"
fi

# ── 注入结束 ──────────────────────────────────────────────────

exit 0
