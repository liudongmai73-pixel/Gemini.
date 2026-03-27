import os
import json
import asyncio
from datetime import datetime, time
from cerebras.cloud.sdk import Cerebras
import google.generativeai as genai
from groq import Groq
from git_manager import GitManager

# ========== 定时任务管理 ==========
scheduled_tasks = {}  # 存储定时任务

async def schedule_daily_message(bot, channel_id, message, hour, minute):
    """每天定时发送消息"""
    while True:
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if now >= target_time:
            target_time = target_time.replace(day=now.day + 1)
        
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        try:
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
                print(f"✅ 定时消息已发送: {message}")
            else:
                print(f"❌ 找不到频道: {channel_id}")
        except Exception as e:
            print(f"❌ 发送定时消息失败: {e}")

# ========== 工具函数 ==========
def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    try:
        gm = GitManager(repo_path=os.getcwd())
        success = gm.apply_patch(patch_text, commit_message)
        if success:
            return "✅ 代码已修改并推送，Railway 将自动重新部署（约1-2分钟）。"
        return "❌ 修改失败，请检查补丁格式。"
    except Exception as e:
        return f"❌ 错误：{str(e)}"

def get_time() -> str:
    now = datetime.now()
    return f"🕐 当前时间：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"

def add_daily_task(channel_id: str, message: str, hour: int, minute: int) -> str:
    """添加每日定时任务"""
    task_id = f"{channel_id}_{hour}_{minute}"
    scheduled_tasks[task_id] = {
        "channel_id": channel_id,
        "message": message,
        "hour": hour,
        "minute": minute
    }
    return f"✅ 已设置每日 {hour:02d}:{minute:02d} 发送消息到频道 {channel_id}"

def list_tasks() -> str:
    """列出所有定时任务"""
    if not scheduled_tasks:
        return "📭 当前没有定时任务"
    
    tasks_list = []
    for task_id, task in scheduled_tasks.items():
        tasks_list.append(f"  - 每日 {task['hour']:02d}:{task['minute']:02d} 发送到 {task['channel_id']}: {task['message'][:50]}")
    
    return "📋 定时任务列表：\n" + "\n".join(tasks_list)

# ========== 工具定义 ==========
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "apply_code_patch",
            "description": "应用代码补丁并推送至 Git 仓库",
            "parameters": {
                "type": "object",
                "properties": {
                    "patch_text": {"type": "string", "description": "diff 格式的补丁内容"},
                    "commit_message": {"type": "string", "description": "提交信息"}
                },
                "required": ["patch_text"]
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
            "name": "add_daily_task",
            "description": "添加每日定时任务，每天固定时间发送消息",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Discord 频道 ID"},
                    "message": {"type": "string", "description": "要发送的消息内容"},
                    "hour": {"type": "integer", "description": "小时 (0-23)"},
                    "minute": {"type": "integer", "description": "分钟 (0-59)"}
                },
                "required": ["channel_id", "message", "hour", "minute"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "列出所有定时任务",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

SYSTEM_INSTRUCTION = """
你是 Discord 机器人。你的职责：

1. **聊天**：正常对话，友好回复。
2. **查询时间**：只有用户明确说"现在几点"、"时间"时，才调用 get_time。
3. **修改代码**：只有用户明确说"改代码"、"修改"、"把XX改成XX"时，才调用 apply_code_patch。
4. **定时任务**：用户说"定时发送"、"每天XX点发消息"时，调用 add_daily_task。

**重要**：
- 不要主动调用任何工具
- 不要猜测用户意图
- 保持对话自然

现在开始！
"""

class Agent:
    def __init__(self):
        self.history = []
        self.pending_patch = None
        self.waiting_for_confirmation = False
        self.bot = None  # 存储 bot 实例
        
        # 初始化各个 API
        self.cerebras_client = None
        self.gemini_client = None
        self.groq_client = None
        
        if os.getenv("CEREBRAS_API_KEY"):
            try:
                self.cerebras_client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))
                self.cerebras_model = "llama-3.3-70b"
                print("✅ Cerebras 已配置")
            except Exception as e:
                print(f"⚠️ Cerebras 配置失败: {e}")
        
        if os.getenv("GOOGLE_API_KEY"):
            try:
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
                print("✅ Gemini 已配置")
            except Exception as e:
                print(f"⚠️ Gemini 配置失败: {e}")
        
        if os.getenv("GROQ_API_KEY"):
            try:
                self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
                print("✅ Groq 已配置")
            except Exception as e:
                print(f"⚠️ Groq 配置失败: {e}")
        
        self.providers = []
        if self.cerebras_client:
            self.providers.append("cerebras")
        if self.gemini_client:
            self.providers.append("gemini")
        if self.groq_client:
            self.providers.append("groq")
        
        if not self.providers:
            raise Exception("❌ 没有可用的 API！")
        
        print(f"🚀 API 调用顺序: {' → '.join(self.providers)}")

    def set_bot(self, bot):
        """设置 bot 实例，用于定时任务"""
        self.bot = bot

    async def start_scheduled_tasks(self):
        """启动所有定时任务"""
        # 这里可以加载保存的任务，目前先空着
        pass

    async def run(self, user_input: str, user_id: str, channel=None) -> str:
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

        if user_input.strip() in ["!reset", "重置", "清除历史"]:
            self.history = []
            self.waiting_for_confirmation = False
            self.pending_patch = None
            return "✅ 对话已重置，历史已清空"

        for provider in self.providers:
            try:
                if provider == "cerebras":
                    result = await self._use_cerebras(user_input, channel)
                elif provider == "gemini":
                    result = await self._use_gemini(user_input)
                elif provider == "groq":
                    result = await self._use_groq(user_input, channel)
                else:
                    continue
                
                if result:
                    return result
                    
            except Exception as e:
                print(f"⚠️ {provider} 失败: {e}")
                continue
        
        return "❌ 所有 API 都失败了，请稍后再试。"

    async def _use_cerebras(self, user_input: str, channel=None) -> str:
        try:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": user_input})

            response = self.cerebras_client.chat.completions.create(
                model=self.cerebras_model,
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
                    
                    if func_name == "apply_code_patch":
                        self.pending_patch = {"patch": args.get("patch_text"), "message": args.get("commit_message", "Self-modify")}
                        self.waiting_for_confirmation = True
                        return f"📝 补丁预览：\n```diff\n{args.get('patch_text')}\n```\n是否应用？回复 yes 或 no"
                    
                    elif func_name == "get_time":
                        result = get_time()
                        self._update_history(user_input, result)
                        return result
                    
                    elif func_name == "add_daily_task":
                        if not self.bot:
                            return "❌ 定时任务需要 bot 实例，请重启机器人"
                        channel_id = args.get("channel_id")
                        message = args.get("message")
                        hour = args.get("hour")
                        minute = args.get("minute")
                        
                        # 启动定时任务
                        asyncio.create_task(schedule_daily_message(
                            self.bot, channel_id, message, hour, minute
                        ))
                        result = add_daily_task(channel_id, message, hour, minute)
                        self._update_history(user_input, result)
                        return result
                    
                    elif func_name == "list_tasks":
                        result = list_tasks()
                        self._update_history(user_input, result)
                        return result
            
            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text
            
        except Exception as e:
            print(f"Cerebras 错误: {e}")
            raise

    async def _use_gemini(self, user_input: str) -> str:
        # Gemini 部分保持原样
        try:
            model = genai.GenerativeModel(
                self.gemini_model,
                system_instruction=SYSTEM_INSTRUCTION
            )
            chat = model.start_chat(history=self.history)
            response = chat.send_message(user_input)
            reply = response.text
            
            if "--- a/" in reply and "+++ b/" in reply:
                import re
                patch_match = re.search(r'(--- a/.*?\n\+\+\+ b/.*?\n@@.*?\n(?:[+- ].*?\n)+)', reply, re.DOTALL)
                if patch_match:
                    self.pending_patch = {"patch": patch_match.group(1), "message": "Self-modify"}
                    self.waiting_for_confirmation = True
                    return reply + "\n\n是否应用？回复 yes 或 no"
            
            self._update_history(user_input, reply)
            return reply
            
        except Exception as e:
            print(f"Gemini 错误: {e}")
            raise

    async def _use_groq(self, user_input: str, channel=None) -> str:
        # Groq 部分添加定时任务支持
        try:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
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
                    
                    if func_name == "apply_code_patch":
                        self.pending_patch = {"patch": args.get("patch_text"), "message": args.get("commit_message", "Self-modify")}
                        self.waiting_for_confirmation = True
                        return f"📝 补丁预览：\n```diff\n{args.get('patch_text')}\n```\n是否应用？回复 yes 或 no"
                    
                    elif func_name == "get_time":
                        result = get_time()
                        self._update_history(user_input, result)
                        return result
                    
                    elif func_name == "add_daily_task":
                        if not self.bot:
                            return "❌ 定时任务需要 bot 实例，请重启机器人"
                        channel_id = args.get("channel_id")
                        message = args.get("message")
                        hour = args.get("hour")
                        minute = args.get("minute")
                        
                        asyncio.create_task(schedule_daily_message(
                            self.bot, channel_id, message, hour, minute
                        ))
                        result = add_daily_task(channel_id, message, hour, minute)
                        self._update_history(user_input, result)
                        return result
                    
                    elif func_name == "list_tasks":
                        result = list_tasks()
                        self._update_history(user_input, result)
                        return result
            
            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text
            
        except Exception as e:
            print(f"Groq 错误: {e}")
            raise

    def _update_history(self, user_input: str, reply: str):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
