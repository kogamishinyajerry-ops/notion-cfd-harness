#!/bin/bash
# Phase4 Code Review 触发脚本（非阻塞版本）
# 用法: ./scripts/trigger_code_review.sh "P4-01实现描述"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_COMPANION="$HOME/.claude/plugins/cache/openai-codex/codex/1.0.2/scripts/codex-companion.mjs"
BASE_COMMIT="${BASE_COMMIT:-HEAD~1}"
SCOPE="${SCOPE:-working-tree}"
FOCUS="${1:-Phase4 Memory Network 实现}"

echo "=== Phase4 Code Review 触发器 ==="
echo "Base: $BASE_COMMIT"
echo "Scope: $SCOPE"
echo "Focus: $FOCUS"
echo ""

# 检查 Codex companion 是否存在
if [ ! -f "$CODEX_COMPANION" ]; then
    echo "⚠️ Codex companion 未找到: $CODEX_COMPANION"
    echo "Code Review 将跳过（不阻塞）"
    exit 0
fi

# 检查 Codex 状态
echo "检查 Codex 状态..."
STATUS_OUTPUT=$(node "$CODEX_COMPANION" status --json 2>&1 || echo "{}")

# 检查是否有额度问题
if echo "$STATUS_OUTPUT" | grep -q "usage limit"; then
    echo "⚠️ Codex 额度不足"
    echo "Code Review 将跳过（不阻塞执行）"
    echo ""
    echo "建议: 等待额度重置后手动触发审查"
    exit 0
fi

# 检查是否有运行中的任务
if echo "$STATUS_OUTPUT" | grep -q '"running".*\[\s*{'; then
    RUNNING_COUNT=$(echo "$STATUS_OUTPUT" | grep -o '"running".*:' | grep -o '\[' | wc -l | tr -d ' ')
    if [ "$RUNNING_COUNT" -gt 0 ]; then
        echo "⚠️ Codex 有 $RUNNING_COUNT 个任务运行中"
        echo "Code Review 将跳过（不阻塞执行）"
        exit 0
    fi
fi

# 尝试触发后台审查
echo "触发 Codex Code Review（后台模式）..."
REVIEW_OUTPUT=$(node "$CODEX_COMPANION" adversarial-review \
    --base "$BASE_COMMIT" \
    --scope "$SCOPE" \
    --focus "$FOCUS" \
    --background 2>&1) || REVIEW_OUTPUT=""

# 检查是否成功触发
if echo "$REVIEW_OUTPUT" | grep -q "thread ready\|Thread ready\|job.*created"; then
    echo "✅ Code Review 已成功触发（后台运行）"
    echo ""
    echo "查看结果命令:"
    echo "  node $CODEX_COMPANION result <job-id>"
    echo ""
    echo "查看所有任务:"
    echo "  node $CODEX_COMPANION status --all"
    exit 0
fi

# 如果触发失败但不是因为额度问题，记录但不阻塞
if echo "$REVIEW_OUTPUT" | grep -q "usage limit"; then
    echo "⚠️ Codex 额度不足"
elif [ -n "$REVIEW_OUTPUT" ]; then
    echo "⚠️ Code Review 触发遇到问题"
    echo "$REVIEW_OUTPUT" | head -3
else
    echo "⚠️ Code Review 触发无返回"
fi

echo ""
echo "Code Review 跳过（不阻塞执行）"
echo "任务将正常提交和推送"
exit 0
