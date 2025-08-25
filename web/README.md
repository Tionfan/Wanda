# 政策问答助手

基于RAG检索与用户画像的智能政策问答系统，提供专业、个性化的政策咨询服务。

## 🌟 功能特点

- **智能问答**：基于RAG技术，从知识库中检索相关政策信息
- **用户画像**：根据用户背景提供个性化回答
- **流式输出**：实时显示AI思考过程和回答内容
- **思考透明**：可查看AI的推理过程
- **记忆功能**：保存对话历史，支持上下文理解
- **响应式设计**：支持桌面端和移动端

## 🏗️ 系统架构

```
frontend/          # 前端界面 (HTML + CSS + JavaScript)
├── index.html     # 主页面
├── style.css      # 样式文件
└── script.js      # 前端逻辑

backend/           # 后端服务 (FastAPI)
├── main.py        # 主服务文件
├── requirements.txt # Python依赖
├── system_prompt.txt # 系统提示模板
├── prompt.txt     # 用户提示模板
└── .env.example   # 环境变量示例

start.sh           # 启动脚本
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- RAG服务 (运行在 localhost:9621)
- 方舟API访问权限
- MemoBase账户

### 2. 安装依赖

```bash
# 克隆项目
cd /root/workspace/WANDA

# 运行启动脚本
./start.sh
```

### 3. 配置环境变量

编辑 `backend/.env` 文件，配置以下信息：

```bash
# 方舟 API Key
ARK_API_KEY=your_ark_api_key_here

# RAG 服务配置
RAG_SERVICE_URL=http://localhost:9621
CHUNK_TOP_K=5

# MemoBase 配置
MEMOBASE_PROJECT_URL=https://api.memobase.dev
MEMOBASE_API_KEY=your_memobase_api_key_here
```

### 4. 启动服务

```bash
./start.sh
```

服务启动后：
- 前端地址：http://localhost:8080
- 后端API：http://localhost:8000

## 📱 使用说明

1. **开始对话**：在输入框中输入政策相关问题
2. **查看思考**：点击"查看AI思考过程"按钮了解推理过程  
3. **连续对话**：支持多轮对话，系统会记住上下文
4. **移动适配**：在手机上也能流畅使用

## 🔧 API接口

### POST /chat
发送聊天消息

**请求体：**
```json
{
  "message": "我想了解创新大赛的政策"
}
```

**响应：** 流式JSON数据
```json
{"type": "reasoning", "content": "思考内容"}
{"type": "answer", "content": "回答内容"}
{"type": "complete"}
```

### GET /health
健康检查

**响应：**
```json
{
  "status": "healthy",
  "service": "政策问答助手API"
}
```

## 🎨 界面特色

- **现代化设计**：渐变背景，圆角卡片，优雅动画
- **响应式布局**：自适应桌面和移动设备
- **实时交互**：流式显示，即时反馈
- **思考透明**：可视化AI推理过程
- **用户友好**：清晰的消息气泡，贴心的使用提示

## 🔄 核心流程

1. **用户输入** → 前端收集用户问题
2. **RAG检索** → 后端查询知识库获取相关政策
3. **画像分析** → 获取用户画像信息
4. **模型推理** → 结合RAG和画像生成回答
5. **流式输出** → 实时显示思考和回答过程
6. **记忆存储** → 保存对话到记忆库

## 🛠️ 技术栈

**前端：**
- 原生HTML/CSS/JavaScript
- 响应式设计
- WebSocket风格的流式交互

**后端：**
- FastAPI (Python异步框架)
- 方舟SDK (大语言模型)
- MemoBase (记忆存储)
- RAG服务集成

## 📝 自定义配置

### 修改提示词模板

编辑 `backend/system_prompt.txt` 和 `backend/prompt.txt` 来自定义AI助手的行为。

### 调整界面样式

修改 `frontend/style.css` 来自定义界面外观。

### 配置RAG服务

在 `.env` 文件中修改 `RAG_SERVICE_URL` 和 `CHUNK_TOP_K`。

## 🚨 注意事项

1. **API密钥安全**：请妥善保管API密钥，不要提交到版本控制
2. **服务依赖**：确保RAG服务正常运行
3. **网络连接**：需要稳定的网络连接访问外部服务
4. **浏览器兼容**：建议使用现代浏览器 (Chrome, Firefox, Safari)

## 🔍 故障排除

### 后端启动失败
- 检查Python环境和依赖安装
- 验证API密钥配置
- 确认RAG服务可访问

### 前端无法连接后端
- 检查后端服务状态
- 验证CORS配置
- 检查网络防火墙设置

### RAG检索失败
- 确认RAG服务运行状态
- 检查服务地址配置
- 验证请求格式

## 📄 许可证

本项目仅供学习和研究使用。

---

💬 **开始您的政策咨询之旅！** 访问 http://localhost:8080
