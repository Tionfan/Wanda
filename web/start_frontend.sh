#!/bin/bash

echo "🌐 启动前端服务..."
cd /root/workspace/WANDA/frontend

# 检查5173端口是否被占用
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口5173已被占用，尝试停止现有服务..."
    pkill -f "python.*http.server.*5173" 2>/dev/null || true
    sleep 2
fi

echo "📱 前端服务启动于: http://localhost:5173"
echo "🔧 请确保后端服务运行在: http://localhost:8080"
echo "按 Ctrl+C 停止服务"
echo ""

python3 -m http.server 5173
