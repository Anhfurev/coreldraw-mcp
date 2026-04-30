#!/usr/bin/env bash
# .harness/hooks/session-end-guard.sh
# Claude Code Stop hook
#
# 机制：
#   exit 0 → 允许 Claude 停止
#   exit 2 → 阻止 Claude 停止，stdout 内容作为反馈发给 Claude
#
# 目标：检查本次 Session 是否已执行 SESSION_END 清单
# 判断依据：今天是否有 session 摘要文件写入 registry/sessions/

HARNESS_DIR=".harness"
SESSION_DIR="$HARNESS_DIR/registry/sessions"
TODAY=$(date +%Y-%m-%d)

# 如果 .harness 不存在，静默放行
[ -d "$HARNESS_DIR" ] || exit 0

# 只在 Claude Code 环境中拦截（opencode 由 harness-opencode-plugin.ts 处理）
[ "${CLAUDE_CODE_HOOKS:-}" = "1" ] || exit 0

# ── 检查今天是否已有 session 摘要 ──────────────────────────────
has_session_today() {
    ls "$SESSION_DIR"/${TODAY}-*.md 2>/dev/null | head -1 | grep -q .
}

# ── 检查 _index.md 今天是否有新条目 ───────────────────────────
has_index_today() {
    [ -f "$HARNESS_DIR/registry/_index.md" ] && \
    grep -q "^\[$TODAY" "$HARNESS_DIR/registry/_index.md"
}

# ── 如果今天已经完成了 SESSION_END，放行 ───────────────────────
if has_session_today || has_index_today; then
    exit 0
fi

# ── 还没做 SESSION_END，拦截并注入清单 ─────────────────────────
cat << 'BLOCK'
╔══════════════════════════════════════════════════════════╗
║  ⚠️  SESSION_END 尚未完成 — 不允许停止                  ║
╚══════════════════════════════════════════════════════════╝

你还没有执行 SESSION_END 清单。在停止之前，必须完成以下工作：

BLOCK

# 注入 SESSION_END 清单
if [ -f "$HARNESS_DIR/SESSION_END.md" ]; then
    cat "$HARNESS_DIR/SESSION_END.md"
else
    cat << 'FALLBACK'
最小化 SESSION_END 要求（SESSION_END.md 文件缺失，执行这些最低要求）：

1. 在 .harness/registry/sessions/ 创建今天的 session 摘要文件
   文件名格式：YYYY-MM-DD-HHmm.md
   （:fix 子模式跳过此步，直接做第 2 步）

2. 在 .harness/registry/_index.md 最前面追加一行：
   [今天日期 时间] [类型] 摘要 → sessions/文件名.md

3. 仅 BUILD / VERIFY 阶段：更新 .harness/state/features.json（把本次完成的 passes 改为 true）
   DISCOVER / DESIGN / PLAN / RELEASE / RETRO 阶段跳过此步。

4. git commit .harness/ 目录

完成后我会允许停止。
FALLBACK
fi

# exit 2 = 阻止停止，强制 Claude 继续执行上面的清单
exit 2
