#!/bin/bash
# ==============================================================
# 一键部署脚本 — AI 小说转剧本工具
# 用法：bash deploy.sh
# 前提：服务器已安装 docker 和 docker-compose
# ==============================================================

set -e

echo "🚀 开始部署 AI 小说转剧本工具..."

# 1. 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在从 .env.example 创建..."
    cp .env.example .env
    echo "❌ 请编辑 .env 文件，填入你的 DEEPSEEK_API_KEY"
    echo "   然后重新运行 bash deploy.sh"
    exit 1
fi

# 2. 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未安装 Docker，请先安装："
    echo "   curl -fsSL https://get.docker.com | bash"
    exit 1
fi

# 3. 构建并启动
echo "🔨 构建 Docker 镜像..."
docker-compose build

echo "🧹 停止旧容器..."
docker-compose down 2>/dev/null || true

echo "✅ 启动服务..."
docker-compose up -d

# 4. 等待健康检查
echo "⏳ 等待服务启动..."
for i in $(seq 1 12); do
    sleep 2
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ 服务已就绪！"
        echo ""
        echo "   访问地址：http://localhost:8000"
        echo "   健康检查：http://localhost:8000/api/health"
        echo ""
        echo "📋 常用命令："
        echo "   查看日志：docker-compose logs -f"
        echo "   重启服务：docker-compose restart"
        echo "   停止服务：docker-compose down"
        exit 0
    fi
done

echo "⚠️  服务启动超时，请检查日志：docker-compose logs"
