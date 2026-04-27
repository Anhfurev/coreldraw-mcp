#!/usr/bin/env bash
# .harness/hooks/codex-session-end-guard.sh
# Codex Stop hook
#
# Codex Stop hook 的输出格式：
#   exit 0  → 允许停止
#   stdout JSON { "continue": false, "stopReason": "..." } → 阻止停止，原因发给 Claude
#
# 与 Claude Code 的 session-end-guard.sh 逻辑相同，只是输出格式不同

HARNESS_DIR=".harness"
SESSION_DIR="$HARNESS_DIR/registry/sessions"
TODAY=$(date +%Y-%m-%d)

[ -d "$HARNESS_DIR" ] || exit 0

# 全新安装（sessions 目录无 .md 文件），放行
real_sessions=$(find "$SESSION_DIR" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
if [ "$real_sessions" -eq 0 ]; then
    exit 0
fi

# 检查今天是否完成
has_done_today() {
    find "$SESSION_DIR" -name "${TODAY}-*.md" 2>/dev/null | grep -q . && return 0
    [ -f "$HARNESS_DIR/registry/_index.md" ] && \
        grep -q "^\[${TODAY}" "$HARNESS_DIR/registry/_index.md" 2>/dev/null && return 0
    return 1
}

has_done_today && exit 0

# 读取 SESSION_END 清单
END_FILE="$HARNESS_DIR/SESSION_END.md"
if [ -f "$END_FILE" ]; then
    END_CONTENT=$(cat "$END_FILE")
else
    END_CONTENT="请完成：\n1. 在 .harness/registry/sessions/ 创建今天的摘要\n2. 更新 _index.md\n3. git commit .harness/"
fi

# Codex Stop hook 输出格式：JSON
# continue: false 阻止停止，stopReason 会作为上下文发给 Claude
python3 - << PYEOF
import json, sys

stop_reason = """SESSION_END 清单尚未完成，请先执行以下步骤：

${END_CONTENT}

完成后 harness 会允许退出。"""

print(json.dumps({
    "continue": False,
    "stopReason": stop_reason
}))
PYEOF
