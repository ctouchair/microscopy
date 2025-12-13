from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import base64
from pathlib import Path
import threading

# 全局变量存储客户端实例和API key
_client_lock = threading.Lock()
_cached_client = None
_cached_api_key = None

# 读取系统提示词和模型名称
def load_system_prompt(prompt_file=None):
    """从 JSON 文件加载系统提示词"""
    if prompt_file is None:
        # 默认路径：microscopy目录下的system_prompt.json
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_file = os.path.join(base_dir, "system_prompt.json")
    
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("system_prompt", "")
    except FileNotFoundError:
        # 如果文件不存在，返回默认提示词
        return "你是一个专业的显微镜图像分析助手。"


def load_model_name(prompt_file=None):
    """从 JSON 文件加载模型名称"""
    if prompt_file is None:
        # 默认路径：microscopy目录下的system_prompt.json
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_file = os.path.join(base_dir, "system_prompt.json")
    
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("model_name", "qwen3-vl-plus")  # 默认模型名称
    except FileNotFoundError:
        return "qwen3-vl-plus"


def load_model_url(prompt_file=None):
    """从 JSON 文件加载模型API URL"""
    if prompt_file is None:
        # 默认路径：microscopy目录下的system_prompt.json
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_file = os.path.join(base_dir, "system_prompt.json")
    
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("model_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")  # 默认URL
    except FileNotFoundError:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"

def get_image_mime_type_from_base64(base64_string):
    """根据base64字符串判断MIME类型，默认为jpeg"""
    # 简单判断，可以根据需要扩展
    return 'image/jpeg'

def get_openai_client():
    """
    获取OpenAI客户端实例（延迟初始化，只初始化一次或API key变化时）
    如果.env文件不存在或VLLM_API_KEY未配置，会返回None
    """
    global _cached_client, _cached_api_key
    
    try:
        # 只在第一次调用时加载.env文件
        if _cached_client is None:
            load_dotenv(override=True)
            api_key = os.getenv("VLLM_API_KEY")
            if not api_key or api_key.strip() == "":
                return None
            
            # 获取模型URL
            model_url = load_model_url()
            
            with _client_lock:
                # 双重检查，避免多线程重复创建
                if _cached_client is None:
                    _cached_client = OpenAI(
                        api_key=api_key,
                        base_url=model_url
                    )
                    _cached_api_key = api_key
        
        return _cached_client
    except Exception as e:
        print(f"创建OpenAI客户端失败: {e}")
        return None


def reset_openai_client():
    """
    重置OpenAI客户端，强制重新加载.env文件并重新初始化客户端
    在API key或模型URL更新时调用此函数
    """
    global _cached_client, _cached_api_key
    
    with _client_lock:
        _cached_client = None
        _cached_api_key = None
    
    # 重新加载.env文件
    load_dotenv(override=True)
    
    # 重新初始化客户端
    api_key = os.getenv("VLLM_API_KEY")
    if api_key and api_key.strip() != "":
        # 获取模型URL
        model_url = load_model_url()
        
        with _client_lock:
            _cached_client = OpenAI(
                api_key=api_key,
                base_url=model_url
            )
            _cached_api_key = api_key

def vllm_chat_stream(image_base64, user_text, conversation_history=None, enable_thinking=True):
    """
    与VLM大模型进行对话，支持流式输出
    
    参数:
        image_base64: base64编码的图片字符串（可选，如果为None则不发送图片）
        user_text: 用户输入的文本
        conversation_history: 对话历史列表，格式为 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        enable_thinking: 是否启用思考过程
    
    返回:
        生成器，每次yield一个字典，包含：
        - 'type': 'thinking' 或 'content' 或 'done'
        - 'content': 文本内容
        - 'is_first': 是否是第一个chunk
    """
    # 构建消息列表
    messages = [
        {
            "role": "system",
            "content": load_system_prompt()
        }
    ]
    
    # 添加对话历史
    if conversation_history:
        messages.extend(conversation_history)
    
    # 构建当前用户消息
    user_content = []
    
    # 如果有图片，添加图片
    if image_base64:
        mime_type = get_image_mime_type_from_base64(image_base64)
        image_data_url = f"data:{mime_type};base64,{image_base64}"
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": image_data_url
            }
        })
    
    # 添加文本（支持纯文本对话，即使没有图片）
    if user_text:
        user_content.append({
            "type": "text",
            "text": user_text
        })
    
    # 确保至少有一个内容（文本或图片）
    if not user_content:
        yield {
            'type': 'error',
            'content': '请提供文本或图片'
        }
        return
    
    messages.append({
        "role": "user",
        "content": user_content
    })
    
    # 创建聊天完成请求
    extra_body = {}
    if enable_thinking:
        extra_body = {
            'enable_thinking': True,
            "thinking_budget": 81920
        }
    
    try:
        # 获取OpenAI客户端（延迟初始化）
        client = get_openai_client()
        if client is None:
            yield {
                'type': 'error',
                'content': 'VLLM_API_KEY未配置。请在前端设置API Key或检查.env文件。'
            }
            return
        
        # 获取模型名称
        model_name = load_model_name()
        
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
            extra_body=extra_body if extra_body else None
        )
        
        is_answering = False
        is_first_chunk = True
        has_content = False
        
        for chunk in completion:
            # 如果chunk.choices为空，可能是usage信息
            if not chunk.choices:
                if hasattr(chunk, 'usage'):
                    yield {
                        'type': 'done',
                        'content': '',
                        'usage': chunk.usage
                    }
                continue
            
            delta = chunk.choices[0].delta
            
            # 处理思考过程
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                yield {
                    'type': 'thinking',
                    'content': delta.reasoning_content,
                    'is_first': is_first_chunk
                }
                is_first_chunk = False
            # 处理回复内容
            elif hasattr(delta, 'content') and delta.content:
                has_content = True
                if not is_answering:
                    is_answering = True
                    is_first_chunk = True
                
                yield {
                    'type': 'content',
                    'content': delta.content,
                    'is_first': is_first_chunk
                }
                is_first_chunk = False
        
        # 发送完成信号（确保总是发送）
        yield {
            'type': 'done',
            'content': '',
            'has_content': has_content
        }
        
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        yield {
            'type': 'error',
            'content': str(e)
        }