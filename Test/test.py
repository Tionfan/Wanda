#%% import信息 函数初始化
import os
import os
# 升级方舟 SDK 到最新版本 pip install -U 'volcengine-python-sdk[ark]'
import re
import threading
import requests
import json
from volcenginesdkarkruntime import Ark
from memobase import MemoBaseClient
from memobase import ChatBlob
# 用户画像函数以及mem0base初始化
def intialize_memo_base():
    """
    初始化MemoBase客户端和用户画像。
    """
    global mem0_client, user_id, messages, user_prompt_template
    user_id = "be8f8272-d386-454e-82dd-bab3f1a19a98"  # 替换为实际的用户ID
    # 初始化mem0base
    mem0_client = MemoBaseClient(
        project_url="https://api.memobase.dev",
        api_key="sk-proj-aaf430e199e59510-ac87f7e368e41929946788b3d7b0c719",
    )
    # Ping the server to check if it's up and running
    assert mem0_client.ping()

def insert(uid,messages):
    u = mem0_client.get_user(uid)
    bid = u.insert(ChatBlob(messages=messages))
    u.flush(sync=True)

def get_profile(uid):
    u = mem0_client.get_user(uid)
    topics = ["interest","basic_info","life_event"]
    return u.profile(need_json=True,only_topics = topics,max_subtopic_size = 5)

def extract_profile_info(data):
    """
    递归地从用户画像数据中提取类型和内容。
    
    Args:
        data (dict): 从服务器获取的用户画像字典。
        
    Returns:
        dict: 一个将画像类型映射到其内容的字典。
    """
    extracted_info = {}
    for key, value in data.items():
        if isinstance(value, dict):
            # 检查这是否是一个包含内容的叶子节点
            if 'content' in value and 'id' in value:
                content = value['content']
                # 移除所有位置的 [mention ...] 标记（无论出现多少次）
                content = re.sub(r'\s*\[mention.*?\]\s*', ' ', content)
                # 清理多余空白符
                content = ' '.join(content.split())
                extracted_info[key] = content
            else:
                # 如果不是叶子节点，则继续向内递归
                nested_info = extract_profile_info(value)
                extracted_info.update(nested_info)
    return extracted_info

def format_profile_for_prompt(extracted_info):
    """
    将提取出的画像信息格式化为适合放入提示词的字符串。
    
    Args:
        extracted_info (dict): 从 extract_profile_info 函数获取的字典。
        
    Returns:
        str: 格式化后的字符串。
    """
    if not extracted_info:
        return "无特定用户画像信息。"
    
    profile_lines = []
    for profile_type, content in extracted_info.items():
        # 将下划线替换为空格并首字母大写，以提高可读性
        type_str = profile_type.replace('_', ' ').capitalize()
        profile_lines.append(f"- {type_str}: {content}")
        
    return "\n".join(profile_lines)
# RAG查询函数
def query_rag(query_text):
    """
    通过HTTP POST请求访问RAG服务以检索知识。

    Args:
        query_text (str): 用户的查询问题。

    Returns:
        str: 从RAG服务获取的知识库文本。
    """
    url = "http://localhost:9621/query"
    headers = {"Content-Type": "application/json"}
    chunk_top_k = os.environ.get("CHUNK_TOP_K")  # 从环境变量获取 chunk_top_k，默认为 5
    data = {"query": "咨询创新大赛", "mode": "naive", "only_need_context": True, "chunk_top_k": chunk_top_k}
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # 如果状态码不是 2xx，则会抛出异常
        # 假设响应是一个JSON，其中包含一个或多个文档，我们将它们连接成一个字符串
        # 您可能需要根据实际的返回格式调整此部分
        results = response.json()
        # 示例处理：将返回的JSON直接转换为格式化的字符串
        # 或者，如果返回的是文档列表，例如: `[{"content": "..."}, ...]`
        # 可以用: `"\n".join(item.get("content", "") for item in results)`
        return json.dumps(results, ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as e:
        print(f"错误：调用RAG服务失败: {e}")
        return "无法连接到知识库。"
    except json.JSONDecodeError:
        print("错误：解析RAG服务响应失败。")
        return "知识库返回了无效的格式。"

def intialize_model():
    global client, system_prompt_template, user_prompt_template, messages
    client = Ark(
        # 从环境变量中读取您的方舟API Key
        api_key=os.environ.get("ARK_API_KEY"), 
        # 深度思考模型耗费时间会较长，请您设置较大的超时时间，避免超时，推荐30分钟以上
        timeout=1800,
        )

    # 读取 prompt 模板
    try:
        with open("system_prompt.txt", "r", encoding="utf-8") as f:
            system_prompt_template = f.read()
        with open("prompt.txt", "r", encoding="utf-8") as f:
            user_prompt_template = f.read()
    except FileNotFoundError as e:
        print(f"错误: {e.filename} 文件未找到。请确保该文件与 test.py 在同一目录下。")
        exit()

    original_profile = get_profile(user_id)
    extracted_info = extract_profile_info(original_profile)
    user_profile = format_profile_for_prompt(extracted_info)
    # user_profile = "身份标签：程序员、已婚、本地户籍\n教育背景：大专学历（市场营销专业）\n数字能力：熟练使用微信、短视频平台，但对政府官网、政务 APP 操作不熟悉，依赖 “刷视频”“问朋友” 获取信息"

    # 使用用户画像填充系统提示模板
    system_message_content = system_prompt_template.replace("{{USER_PROFILE}}", user_profile)

    # 初始化对话历史，并加入系统提示
    messages = [
        {"role": "system", "content": system_message_content}
    ]
    # print(messages)
#%% 测试用户画像函数
# test_profile = get_profile(user_id)
# # print(f"用户 {user_id} 的画像信息: {test_profile}")
# extracted_info = extract_profile_info(test_profile)
# formatted_profile = format_profile_for_prompt(extracted_info)
# print(f"格式化后的用户画像信息:\n{formatted_profile}")
# 初始化模型

#%% 测试RAG
# """
# 通过HTTP POST请求访问RAG服务以检索知识。

# Args:
#     query_text (str): 用户的查询问题。

# Returns:
#     str: 从RAG服务获取的知识库文本。
# """
# url = "http://localhost:9621/query"
# headers = {"Content-Type": "application/json"}
# chunk_top_k = os.environ.get("CHUNK_TOP_K")  # 从环境变量获取 chunk_top_k，默认为 5
# data = {"query": "咨询创新大赛", "mode": "naive", "only_need_context": True, "chunk_top_k": chunk_top_k}

# try:
#     response = requests.post(url, headers=headers, data=json.dumps(data))
#     response.raise_for_status()  # 如果状态码不是 2xx，则会抛出异常
#     # 假设响应是一个JSON，其中包含一个或多个文档，我们将它们连接成一个字符串
#     # 您可能需要根据实际的返回格式调整此部分
#     results = response.json()
#     # 示例处理：将返回的JSON直接转换为格式化的字符串
#     # 或者，如果返回的是文档列表，例如: `[{"content": "..."}, ...]`
#     # 可以用: `"\n".join(item.get("content", "") for item in results)`
#     json.dumps(results, ensure_ascii=False, indent=2)
#     print("知识库返回内容：")
#     print(results)
# except requests.exceptions.RequestException as e:
#     print(f"错误：调用RAG服务失败: {e}")
# except json.JSONDecodeError:
#     print("错误：解析RAG服务响应失败。")

#%% 主函数
def main():
    intialize_memo_base()
    intialize_model()
    while True:
        try:
            # 从命令行获取用户输入
            user_input = input("您: ")
            if user_input.lower() in ["exit", "quit"]:
                print("再见！")
                break

            # 每次都从RAG服务获取最新的知识
            rag_knowledge_base = query_rag(user_input)
            
            # 填充 prompt 模板
            filled_prompt = user_prompt_template.replace("{{RAG_KNOWLEDGE_BASE}}", rag_knowledge_base)
            filled_prompt = filled_prompt.replace("{{USER_QUESTION}}", user_input)

            # 准备本次调用模型所需的消息列表
            # 复制基础历史消息（包含系统消息和之前的对话）
            messages_for_model = list(messages)
            # 将填充了RAG知识的完整prompt作为当前用户消息添加
            messages_for_model.append({"role": "user", "content": filled_prompt})

            # 用于长期记忆和存储的对话历史，只保存用户的原始输入
            memory = [{"role": "user", "content": user_input}]
            # print("messages_for_model:", messages_for_model)
            response = client.chat.completions.create(
                # 指定您创建的方舟推理接入点 ID
                model="ep-20250724160144-rtzxn",
                # 使用为本次调用特制的、包含RAG知识的消息列表
                messages=messages_for_model,
                thinking={
                    "type": "auto", # 模型自行判断是否使用深度思考能力
                },
                stream=True,
            )

            reasoning_content = ""
            assistant_response = ""
            print("政策问答助手: ", end="")
            reasoning_cnt = 0
            answer_cnt = 0
            with response: 
                for chunk in response:
                    if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                        if reasoning_cnt == 0:
                            print("\n思考过程：\n")
                        reasoning_cnt += 1
                        reasoning_content += chunk.choices[0].delta.reasoning_content
                        print(chunk.choices[0].delta.reasoning_content, end="")
                    elif chunk.choices[0].delta.content is not None:
                        if answer_cnt == 0:
                            print("\n回答内容：\n")
                        answer_cnt += 1
                        assistant_response += chunk.choices[0].delta.content
                        print(chunk.choices[0].delta.content, end="")
            print()

            # 将用户的原始提问和模型的完整回复添加到长期对话历史中
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": assistant_response})
            
            # 更新记忆库
            memory.append({"role": "assistant", "content": assistant_response})
            insert_thread = threading.Thread(target=insert, args=(user_id, memory))
            insert_thread.start()
            
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break
#%%
if __name__ == "__main__":
    main()
