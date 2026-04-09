#!/bin/bash
# .claude/hooks/install.sh
# 安装 Git hooks 到 .git/hooks/

set -e

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_HOOKS_DIR=".git/hooks"

echo "📦 Installing Git hooks..."

# 确保 .git/hooks 存在
mkdir -p "$GIT_HOOKS_DIR"

# 复制 hooks
for hook in pre-commit post-commit pre-push; do
    src="$HOOKS_DIR/$hook"
    dst="$GIT_HOOKS_DIR/$hook"

    if [ -f "$src" ]; then
        cp "$src" "$dst"
        chmod +x "$dst"
        echo "  ✓ $hook"
    else
        echo "  ⚠️  $hook not found"
    fi
done

echo ""
echo "✓ Git hooks installed to $GIT_HOOKS_DIR"
echo ""
echo "Installed hooks:"
echo "  • pre-commit  - Sync task status to Notion before commit"
echo "  • post-commit - Sync commit info to Notion after commit"
echo "  • pre-push    - Run tests and checks before push"
echo ""
echo "To bypass hooks temporarily, use:"
echo "  git commit --no-verify"
echo "  git push --no-verify"
