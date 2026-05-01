#!/usr/bin/env bash
# .harness/hooks/guard-dangerous.sh
# PreToolUse hook（Bash 命令拦截）
# exit 0 = 放行，exit 2 = 阻止（stdout 内容发给 Claude）

# 从 stdin 读取 JSON（Claude Code 传入工具调用信息）
INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('tool_input',{}).get('command',''))
except: print('')
" 2>/dev/null)

# ── 拦截规则 ──────────────────────────────────────────────────

# 1. 禁止强制删除
if echo "$CMD" | grep -qE 'rm\s+-rf\s+/|rm\s+--force.*\/'; then
    echo "[harness] ❌ 拦截：rm -rf / 类危险命令，请确认目标路径后重试"
    exit 2
fi

# 2. 禁止修改 features.json 的 description（只允许改 passes）
if echo "$CMD" | grep -qE '(sed|awk|perl).*features\.json.*description'; then
    echo "[harness] ❌ 拦截：不允许修改 features.json 的 description 字段"
    echo "           只允许把 passes 从 false 改为 true"
    exit 2
fi

# 3. 如果是 git commit，检查 commit message 格式
if echo "$CMD" | grep -qE 'git commit'; then
    MSG=$(echo "$CMD" | grep -oP '(?<=-m ["\x27])[^"'\'']+' || echo "")
    if [ -n "$MSG" ] && ! echo "$MSG" | grep -qE '^(feat|fix|docs|refactor|test|chore|style|perf|session|discover|design|verify|release|retro):'; then
        echo "[harness] ⚠️  commit message 格式建议：<type>: <描述>"
        echo "           type 可选：feat/fix/docs/refactor/test/chore/style/perf/session/discover/design/verify/release/retro"
        # 这里是 warning，不拦截（exit 0 放行）
    fi
fi

exit 0
