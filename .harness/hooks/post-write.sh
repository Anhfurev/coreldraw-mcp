#!/usr/bin/env bash
# .harness/hooks/post-write.sh
# PostToolUse hook（文件写入后触发，async 模式，不阻塞 Claude）
# 用途：写入完成后做轻量检查，输出提示（不用 exit 2 阻塞）

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    # Write 工具用 file_path，Edit/MultiEdit 也类似
    print(d.get('tool_input',{}).get('file_path',''))
except: print('')
" 2>/dev/null)

[ -z "$FILE" ] && exit 0

# ── features.json 写入后验证格式 ──────────────────────────────
if echo "$FILE" | grep -q "features\.json"; then
    FILE="$FILE" python3 -c "
import json, sys, os
try:
    d = json.load(open(os.environ['FILE']))
    # 检查是否有 description 被删除或修改（简单检查 features 数组不为空）
    features = d.get('features', [])
    for f in features:
        if not f.get('description'):
            print('[harness] ⚠️  警告：features.json 中有条目缺少 description 字段')
            sys.exit(1)
    print('[harness] ✓ features.json 格式正常')
except json.JSONDecodeError as e:
    print(f'[harness] ❌ features.json JSON 格式错误：{e}')
except Exception as e:
    print(f'[harness] ⚠️  features.json 检查异常：{e}')
" 2>/dev/null
fi

# ── _index.md 写入后提示 ──────────────────────────────────────
if echo "$FILE" | grep -q "_index\.md"; then
    echo "[harness] ✓ registry 索引已更新"
fi

exit 0
