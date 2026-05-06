#!/usr/bin/env bash
# .harness/hooks/session-end.sh
# Claude Code Stop hook — 触发 SESSION_END 协议
# exit 0 = 允许停止；exit 2 = 阻断停止并将 stdout 注入为 additionalContext

HARNESS_DIR=".harness"
PROJECT_HASH=$(printf '%s' "$PWD" | cksum | awk '{print $1}')
FLAG="/tmp/harness-session-end-${PROJECT_HASH}"

# 没有 .harness 目录 → 不是 harness 项目，放行
[ -d "$HARNESS_DIR" ] || exit 0

# 只在 Claude Code 环境中触发
[ "${CLAUDE_CODE_HOOKS:-}" = "1" ] || exit 0

# 注入 SESSION_END 协议并阻断停止
if [ -f "$HARNESS_DIR/SESSION_END.md" ]; then
    if [ -f "$FLAG" ]; then
        echo "## Session_End已提示，结束"
        rm "$FLAG"
        exit 0
    fi
    echo "## Session 停止提示"
    touch "$FLAG"
    cat "$HARNESS_DIR/SESSION_END.md"
    exit 2
fi

echo "## Session 结束提示"
echo "SESSION_END.md 不存在，请手动完成 session 收尾工作。"
exit 0
