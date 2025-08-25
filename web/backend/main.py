from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import os
import re
import threading
import requests
from volcenginesdkarkruntime import Ark
from memobase import MemoBaseClient, ChatBlob

app = FastAPI(title="政策问答助手API", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
mem0_client = None
user_id = "be8f8272-d386-454e-82dd-bab3f1a19a98"
messages = []
client = None
system_prompt_template = ""
user_prompt_template = ""

class ChatMessage(BaseModel):
    message: str

def initialize_memo_base():
    """初始化MemoBase客户端和用户画像"""
    global mem0_client
    mem0_client = MemoBaseClient(
        project_url="https://api.memobase.dev",
        api_key="sk-proj-aaf430e199e59510-ac87f7e368e41929946788b3d7b0c719",
    )
    assert mem0_client.ping()

def insert(uid, messages):
    """插入对话到记忆库"""
    u = mem0_client.get_user(uid)
    bid = u.insert(ChatBlob(messages=messages))
    u.flush(sync=True)

def get_profile(uid):
    """获取用户画像"""
    u = mem0_client.get_user(uid)
    topics = ["interest","basic_info","life_event"]
    return u.profile(need_json=True,only_topics = topics,max_subtopic_size = 5)

def extract_profile_info(data):
    """递归地从用户画像数据中提取类型和内容"""
    extracted_info = {}
    for key, value in data.items():
        if isinstance(value, dict):
            if 'content' in value and 'id' in value:
                content = value['content']
                content = re.sub(r'\s*\[mention.*?\]\s*', ' ', content)
                content = ' '.join(content.split())
                extracted_info[key] = content
            else:
                nested_info = extract_profile_info(value)
                extracted_info.update(nested_info)
    return extracted_info

def format_profile_for_prompt(extracted_info):
    """将提取出的画像信息格式化为适合放入提示词的字符串"""
    if not extracted_info:
        return "无特定用户画像信息。"
    
    profile_lines = []
    for profile_type, content in extracted_info.items():
        type_str = profile_type.replace('_', ' ').capitalize()
        profile_lines.append(f"- {type_str}: {content}")
        
    return "\n".join(profile_lines)

def query_rag(query_text):
    """通过HTTP POST请求访问RAG服务以检索知识"""
    url = "http://localhost:9621/query"
    headers = {"Content-Type": "application/json"}
    chunk_top_k = os.environ.get("CHUNK_TOP_K", "5")
    data = {
        "query": query_text,  # 使用实际的查询文本
        "mode": "naive", 
        "only_need_context": True, 
        "chunk_top_k": int(chunk_top_k)
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        results = response.json()
        return json.dumps(results, ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        print(f"错误：调用RAG服务失败: {e}")
        return "无法连接到知识库。"
    except json.JSONDecodeError:
        print("错误：解析RAG服务响应失败。")
        return "知识库返回了无效的格式。"

def initialize_model():
    """初始化模型和提示模板"""
    global client, system_prompt_template, user_prompt_template, messages
    
    client = Ark(
        api_key=os.environ.get("ARK_API_KEY"),
        timeout=1800,
    )

    # 读取 prompt 模板
    try:
        with open("system_prompt.txt", "r", encoding="utf-8") as f:
            system_prompt_template = f.read()
        with open("prompt.txt", "r", encoding="utf-8") as f:
            user_prompt_template = f.read()
    except FileNotFoundError as e:
        print(f"错误: {e.filename} 文件未找到")
        # 使用默认模板
        system_prompt_template = """你是一个专业的政策问答助手，具有以下特点：
1. 基于用户画像：{{USER_PROFILE}}
2. 能够准确解答政策相关问题
3. 回答简洁明确，逻辑清晰
4. 当遇到不确定的问题时，会诚实地表示不知道

请根据用户的问题和提供的知识库内容，给出准确、有帮助的回答。"""
        
        user_prompt_template = """根据以下知识库内容回答用户问题：

知识库内容：
{{RAG_KNOWLEDGE_BASE}}

用户问题：{{USER_QUESTION}}

请基于知识库内容给出准确的回答，如果知识库中没有相关信息，请说明无法找到相关政策信息。"""

    # 获取用户画像
    try:
        original_profile = get_profile(user_id)
        extracted_info = extract_profile_info(original_profile)
        user_profile = format_profile_for_prompt(extracted_info)
    except Exception as e:
        print(f"获取用户画像失败: {e}")
        user_profile = "暂无用户画像信息"

    # 使用用户画像填充系统提示模板
    system_message_content = system_prompt_template.replace("{{USER_PROFILE}}", user_profile)

    # 初始化对话历史
    messages = [
        {"role": "system", "content": system_message_content}
    ]

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    try:
        initialize_memo_base()
        initialize_model()
        print("✅ 初始化完成")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")

@app.post("/chat")
async def chat(chat_message: ChatMessage):
    """处理聊天消息"""
    try:
        user_input = chat_message.message.strip()
        if not user_input:
            raise HTTPException(status_code=400, detail="消息不能为空")

        # 获取RAG知识
        rag_knowledge_base = query_rag(user_input)
        
        # 填充 prompt 模板
        filled_prompt = user_prompt_template.replace("{{RAG_KNOWLEDGE_BASE}}", rag_knowledge_base)
        filled_prompt = filled_prompt.replace("{{USER_QUESTION}}", user_input)

        # 准备消息列表
        messages_for_model = list(messages)
        messages_for_model.append({"role": "user", "content": filled_prompt})

        # 调用模型
        response = client.chat.completions.create(
            model="ep-20250724160144-rtzxn",
            messages=messages_for_model,
            thinking={"type": "auto"},
            stream=True,
        )

        async def generate_response():
            reasoning_content = ""
            assistant_response = ""
            reasoning_sent = False
            answer_started = False

            try:
                with response:
                    for chunk in response:
                        # 处理思考内容
                        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                            reasoning_content += chunk.choices[0].delta.reasoning_content
                            if not reasoning_sent:
                                # 发送思考开始标志
                                yield f'{json.dumps({"type": "reasoning_start"})}\n'
                                reasoning_sent = True
                            
                            # 流式发送思考内容
                            yield f'{json.dumps({"type": "reasoning", "content": chunk.choices[0].delta.reasoning_content})}\n'
                        
                        # 处理回答内容
                        elif chunk.choices[0].delta.content is not None:
                            if not answer_started:
                                # 发送回答开始标志
                                yield f'{json.dumps({"type": "answer_start"})}\n'
                                answer_started = True
                            
                            assistant_response += chunk.choices[0].delta.content
                            
                            # 流式发送回答内容
                            yield f'{json.dumps({"type": "answer", "content": chunk.choices[0].delta.content})}\n'

                # 更新对话历史
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": assistant_response})
                
                # 更新记忆库（异步执行）
                memory = [
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": assistant_response}
                ]
                threading.Thread(target=insert, args=(user_id, memory)).start()
                
                # 发送完成标志
                yield f'{json.dumps({"type": "complete"})}\n'

            except Exception as e:
                yield f'{json.dumps({"type": "error", "content": str(e)})}\n'

        return StreamingResponse(
            generate_response(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "政策问答助手API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
