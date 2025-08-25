#!/bin/bash

# 启动政策问答助手前端和后端服务

echo "🚀 启动政策问答助手服务..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python3"
    exit 1
fi

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  建议在虚拟环境中运行，继续安装依赖..."
fi

# 进入后端目录并安装依赖
cd backend
echo "📦 安装后端依赖..."
pip install -r requirements.txt

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "📝 创建环境变量文件..."
    cp .env.example .env
    echo "⚠️  请编辑 backend/.env 文件，配置您的API密钥"
    echo "   需要配置："
    echo "   - ARK_API_KEY: 您的方舟API密钥"
    echo "   - MEMOBASE_API_KEY: 您的MemoBase API密钥"
    echo ""
    read -p "是否已经配置好API密钥？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "请先配置API密钥后再运行 ./start.sh"
        exit 1
    fi
fi

# 加载环境变量
export $(cat .env | xargs)

echo "🔧 启动后端服务..."
# 在后台启动后端服务
python main.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 检查后端是否启动成功
if ! curl -s http://localhost:8080/health > /dev/null; then
    echo "❌ 后端服务启动失败"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo "✅ 后端服务启动成功 (PID: $BACKEND_PID)"

# 进入前端目录
cd ../frontend

# 检查是否有HTTP服务器
if command -v python3 &> /dev/null; then
    echo "🌐 启动前端服务..."
    echo "📱 前端地址: http://localhost:5173"
    echo "🔧 后端地址: http://localhost:8080"
    echo ""
    echo "按 Ctrl+C 停止所有服务"
    
    # 启动前端服务
    python3 -m http.server 5173
else
    echo "❌ 无法启动前端服务，请安装Python3或其他HTTP服务器"
fi

# 清理后台进程
echo "🛑 停止服务..."
kill $BACKEND_PID 2>/dev/null
echo "✅ 服务已停止"
