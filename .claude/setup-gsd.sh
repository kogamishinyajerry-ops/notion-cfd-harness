#!/usr/bin/env bash
#
# GSD 初始化脚本
#
# 一键设置完整的 GSD 开发环境
#

set -e

# 颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════╗"
echo "║     GSD - Guided Software Development          ║"
echo "║     初始化开发环境                              ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${NC}"

# 步骤 1: 安装 Git hooks
echo -e "${GREEN}📦 [1/4] 安装 Git hooks...${NC}"
"$PROJECT_ROOT/.claude/hooks/install.sh"

# 步骤 2: 检查 Notion 配置
echo -e "${GREEN}📝 [2/4] 检查 Notion 配置...${NC}"
NOTION_CONFIG="$PROJECT_ROOT/.claude/notion/config.json"

if [ -f "$NOTION_CONFIG" ]; then
    # 检查是否已配置
    if grep -q '"integration_token": ""' "$NOTION_CONFIG"; then
        echo -e "${YELLOW}⚠️  Notion 未完全配置${NC}"
        echo ""
        echo "请按以下步骤配置 Notion 集成:"
        echo "  1. 访问 https://www.notion.so/my-integrations"
        echo "  2. 创建新的 Integration，复制 Token"
        echo "  3. 在 Notion 中创建 Tasks 和 Design Docs 数据库"
        echo "  4. 复制数据库 ID"
        echo "  5. 更新 $NOTION_CONFIG"
        echo ""
        echo "💡 跳过 Notion 配置也可使用 GSD (本地模式)"
    else
        echo -e "${GREEN}✓ Notion 已配置${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Notion 配置文件不存在${NC}"
fi

# 步骤 3: 创建必要的目录
echo -e "${GREEN}📁 [3/4] 创建目录结构...${NC}"
mkdir -p "$PROJECT_ROOT/design/.notion-sync"
mkdir -p "$PROJECT_ROOT/tasks/.notion-sync"
mkdir -p "$PROJECT_ROOT/.claude/memory"
echo -e "${GREEN}✓ 目录结构已创建${NC}"

# 步骤 4: 初始化 Python 依赖
echo -e "${GREEN}🐍 [4/4] 检查 Python 依赖...${NC}"
if command -v pip3 &> /dev/null; then
    echo "安装 Python 依赖..."
    pip3 install --quiet requests pytest pytest-cov black isort mypy flake8 2>/dev/null || true
    echo -e "${GREEN}✓ Python 依赖已安装${NC}"
else
    echo -e "${YELLOW}⚠️  pip3 未找到，请手动安装依赖${NC}"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════╗"
echo "║              ✅ GSD 初始化完成!                      ║"
echo "╚════════════════════════════════════════════════╝${NC}"
echo ""
echo "📚 快速开始:"
echo "  1. 阅读规范: cat $PROJECT_ROOT/GSD.md"
echo "  2. 配置 Notion (可选): 编辑 $NOTION_CONFIG"
echo "  3. 开始开发: Git hooks 会自动检查"
echo ""
echo "🔧 常用命令:"
echo "  .claude/notion/sync.py status    - 查看 Notion 配置状态"
echo "  .claude/notion/sync.py sync-commit - 同步 commit 到 Notion"
echo "  .claude/notion/sync.py create-review --reason \"原因\""
echo ""
echo "💡 Claude 会自动遵循 GSD 规范"
echo "   - 关键点会停下来让你介入"
echo "   - 文档先行设计"
echo "   - 质量门控自动检查"
