#!/usr/bin/env bash
# .harness/hooks/session-start.sh
# Claude Code SessionStart hook
# 返回的 stdout 会作为 additionalContext 注入到 Claude 的上下文里
# 不需要 exit code 控制（SessionStart 无法阻止启动）

HARNESS_DIR=".harness"

# 如果 .harness 目录不存在，静默退出（项目还没初始化）
[ -d "$HARNESS_DIR" ] || exit 0

# ── 注入内容开始 ──────────────────────────────────────────────
cat << 'HEADER'
╔══════════════════════════════════════════════════════╗
║          HARNESS SESSION START — 自动加载            ║
╚══════════════════════════════════════════════════════╝
HEADER

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
