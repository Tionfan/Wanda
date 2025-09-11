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
    """通过HTTP POST请求访问RAG服务以检索知识，并提取Document Chunks部分"""
    url = "http://localhost:9621/query"
    headers = {"Content-Type": "application/json"}
    chunk_top_k = os.environ.get("CHUNK_TOP_K", "5")
    data = {
        "query": query_text,  # 使用实际的查询文本
        "mode": "hybrid", 
        "only_need_context": True, 
        "chunk_top_k": int(chunk_top_k)
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        results = response.json()
        
        # 提取Document Chunks部分
        if 'response' in results:
            response_text = results['response']
            dc_pattern = r'-----Document Chunks\(DC\)-----\s*\n\s*```json\s*(.*?)\s*```'
            dc_match = re.search(dc_pattern, response_text, re.DOTALL)
            
            if dc_match:
                document_chunks = dc_match.group(1)
                try:
                    # 尝试解析JSON，确保它是有效的JSON
                    chunks_json = json.loads(document_chunks)
                    # 返回提取出的Document Chunks部分
                    return json.dumps(chunks_json, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    print("警告：无法解析Document Chunks部分的JSON")
                    # 返回原始文本块
                    return document_chunks
            
        # 如果没有找到Document Chunks部分或格式不对，返回整个结果
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
    system_prompt_template = """你是个专门为用户解决问题的助手"""
    user_prompt_template = """根据以下知识库内容回答用户问题：
知识库内容：
{{RAG_KNOWLEDGE_BASE}}

用户问题：{{USER_QUESTION}}

请基于知识库内容给出准确的回答，如果知识库中没有相关信息，请说明无法找到相关信息。"""

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    try:
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
