import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from groq import Groq
import google.generativeai as genai
from together import Together
from git_manager import GitManager
from datetime import datetime, timedelta
import threading
import time

# ========== 工具函数定义 ==========

def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    """应用代码补丁并推送至 Git 仓库"""
    try:
        gm = GitManager(repo_path=os.getcwd())
        success = gm.apply_patch(patch_text, commit_message)
        if success:
            return "✅ 代码已修改并推送，Railway 将自动重新部署（约1-2分钟）。"
        else:
            return "❌ 修改失败，请检查补丁格式。"
    except Exception as e:
        return f"❌ 错误：{str(e)}"

def read_file(filepath: str) -> str:
    """读取文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 1900:
                content = content[:1900] + "\n... (文件过长，已截断)"
            return f"📄 文件 {filepath} 的内容：\n```\n{content}\n```"
    except FileNotFoundError:
        return f"❌ 文件不存在: {filepath}"
    except Exception as e:
        return f"❌ 读取失败: {str(e)}"

def write_file(filepath: str, content: str) -> str:
    """写入文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ 文件已保存: {filepath}"
    except Exception as e:
        return f"❌ 保存失败: {str(e)}"

def list_files(directory: str = ".") -> str:
    """列出目录中的文件"""
    try:
        files = os.listdir(directory)
        file_list = "\n".join(f"  - {f}" for f in files[:20])
        return f"📁 {directory} 目录下的文件：\n{file_list}"
    except Exception as e:
        return f"❌ 列出失败: {str(e)}"

def delete_file(filepath: str) -> str:
    """删除文件"""
    try:
        os.remove(filepath)
        return f"✅ 文件已删除: {filepath}"
    except Exception as e:
        return f"❌ 删除失败: {str(e)}"

def search_web(query: str) -> str:
    """联网搜索（使用 DuckDuckGo）"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        for result in soup.find_all('a', class_='result__a')[:5]:
            title = result.get_text()
            link = result.get('href')
            if link and link.startswith('/'):
                link = 'https://duckduckgo.com' + link
            results.append(f"🔗 {title}\n   {link}")
        
        if results:
            return "🔍 搜索结果：\n\n" + "\n\n".join(results)
        else:
            return "❌ 没有找到相关结果"
    except Exception as e:
        return f"❌ 搜索失败: {str(e)}"

def fetch_url(url: str) -> str:
    """网络请求：获取网页内容"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        content = response.text[:1900]
        return f"🌐 网页内容：\n```\n{content}\n```"
    except Exception as e:
        return f"❌ 请求失败: {str(e)}"

def get_weather(city: str) -> str:
    """获取天气"""
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%w"
        response = requests.get(url, timeout=10)
        weather = response.text.strip()
        return f"🌤️ {city} 天气：{weather}"
    except Exception as e:
        return f"❌ 获取天气失败: {str(e)}"

def get_time() -> str:
    """获取当前时间"""
    now = datetime.now()
    return f"🕐 当前时间：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"

def set_reminder(message: str, seconds: int) -> str:
    """设置提醒（定时任务）"""
    def remind():
        time.sleep(seconds)
        # 这里需要发送到 Discord，暂时返回消息
        print(f"⏰ 提醒：{message}")
    
    thread = threading.Thread(target=remind)
    thread.daemon = True
    thread.start()
    return f"✅ 已设置 {seconds} 秒后的提醒：{message}"

# ========== 工具定义 ==========

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "apply_code_patch",
            "description": "应用代码补丁并推送至 Git 仓库，实现自我修改",
            "parameters": {
                "type": "object",
                "properties": {
                    "patch_text": {"type": "string", "description": "统一 diff 格式的补丁内容"},
                    "commit_message": {"type": "string", "description": "提交信息"}
                },
                "required": ["patch_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "文件路径"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "文件内容"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出目录中的文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "目录路径，默认为当前目录"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "文件路径"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "联网搜索，获取最新信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "网络请求，获取网页内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页URL"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取城市天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前时间",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "设置提醒（定时任务）",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "提醒内容"},
                    "seconds": {"type": "integer", "description": "多少秒后提醒"}
                },
                "required": ["message", "seconds"]
            }
        }
    }
]

SYSTEM_INSTRUCTION = """
你是一个功能强大的 Discord 机器人，拥有以下能力：

1. **普通对话**：回答问题、帮助用户
2. **自我修改代码**：修改自己的代码并推送
3. **文件管理**：读取、写入、列出、删除文件
4. **联网搜索**：搜索最新信息
5. **网络请求**：获取网页内容
6. **天气查询**：获取城市天气
7. **时间查询**：获取当前时间
8. **定时任务**：设置提醒

**重要规则**：
- 修改代码前必须先展示补丁，等待用户确认
- 使用中文回复，友好、有帮助

现在开始！
"""

class Agent:
    def __init__(self):
        self.history = []
        self.providers = []
        self.pending_patch = None
        self.waiting_for_confirmation = False
        
        # 配置 Gemini
        if os.getenv("GOOGLE_API_KEY"):
            try:
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
                self.providers.append("gemini")
                print("✅ Gemini 已配置")
            except Exception as e:
                print(f"⚠️ Gemini 配置失败: {e}")
        
        # 配置 Groq
        if os.getenv("GROQ_API_KEY"):
            try:
                self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                self.groq_model = "llama-3.3-70b-versatile"
                self.providers.append("groq")
                print("✅ Groq 已配置")
            except Exception as e:
                print(f"⚠️ Groq 配置失败: {e}")
        
        # 配置 Together
        if os.getenv("TOGETHER_API_KEY"):
            try:
                self.together_client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
                self.together_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
                self.providers.append("together")
                print("✅ Together 已配置")
            except Exception as e:
                print(f"⚠️ Together 配置失败: {e}")
        
        if not self.providers:
            raise Exception("❌ 没有可用的 API！")
        
        self.current_provider = self.providers[0]
        print(f"🚀 默认使用: {self.current_provider}")

    async def run(self, user_input: str, user_id: str) -> str:
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        if self.waiting_for_confirmation:
            if user_input.lower() in ["yes", "是", "确认", "同意", "y"]:
                result = apply_code_patch(self.pending_patch["patch"], self.pending_patch.get("message", "Self-modify"))
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return result
            elif user_input.lower() in ["no", "不", "取消", "n"]:
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return "❌ 已取消修改。"
            else:
                return "请回复 yes 确认修改，或 no 取消。"

        for provider in self.providers:
            if provider == "gemini":
                reply = await self._use_gemini(user_input)
            elif provider == "groq":
                reply = await self._use_groq(user_input)
            elif provider == "together":
                reply = await self._use_together(user_input)
            else:
                continue
            
            if reply:
                self.current_provider = provider
                return reply
            
            print(f"⚠️ {provider} 失败，尝试下一个...")
        
        return "❌ 所有 API 都失败了，请稍后再试。"

    async def _use_gemini(self, user_input: str) -> str:
        try:
            model = genai.GenerativeModel(self.gemini_model, system_instruction=SYSTEM_INSTRUCTION)
            chat = model.start_chat(history=self.history)
            response = chat.send_message(user_input)
            reply = response.text
            self._update_history(user_input, reply)
            return reply
        except Exception as e:
            print(f"Gemini 错误: {e}")
            return None

    async def _use_groq(self, user_input: str) -> str:
        try:
            messages = []
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": user_input})
            
            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                temperature=0.7,
                max_tokens=8192,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            reply = response.choices[0].message
            
            if reply.tool_calls:
                for tool_call in reply.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    # 执行对应的函数
                    if func_name == "apply_code_patch":
                        self.pending_patch = {"patch": args.get("patch_text"), "message": args.get("commit_message", "Self-modify")}
                        self.waiting_for_confirmation = True
                        return f"📝 补丁预览：\n```diff\n{args.get('patch_text')}\n```\n是否应用？回复 yes 或 no"
                    elif func_name == "read_file":
                        result = read_file(args.get("filepath"))
                    elif func_name == "write_file":
                        result = write_file(args.get("filepath"), args.get("content"))
                    elif func_name == "list_files":
                        result = list_files(args.get("directory", "."))
                    elif func_name == "delete_file":
                        result = delete_file(args.get("filepath"))
                    elif func_name == "search_web":
                        result = search_web(args.get("query"))
                    elif func_name == "fetch_url":
                        result = fetch_url(args.get("url"))
                    elif func_name == "get_weather":
                        result = get_weather(args.get("city"))
                    elif func_name == "get_time":
                        result = get_time()
                    elif func_name == "set_reminder":
                        result = set_reminder(args.get("message"), args.get("seconds"))
                    else:
                        result = f"未知函数: {func_name}"
                    
                    self._update_history(user_input, result)
                    return result
            
            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text
            
        except Exception as e:
            print(f"Groq 错误: {e}")
            return None

    async def _use_together(self, user_input: str) -> str:
        try:
            messages = []
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": user_input})
            
            response = self.together_client.chat.completions.create(
                model=self.together_model,
                messages=messages,
                temperature=0.7,
                max_tokens=8192
            )
            
            reply = response.choices[0].message.content
            self._update_history(user_input, reply)
            return reply
            
        except Exception as e:
            print(f"Together 错误: {e}")
            return None

    def _update_history(self, user_input: str, reply: str):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
