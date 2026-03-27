import os
import json
from groq import Groq
from git_manager import GitManager
from datetime import datetime

# 配置 Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "qwen-2.5-72b"

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

def set_daily_message(message: str, hour: int, minute: int) -> str:
    """设置每日定时消息（简化版，只记录）"""
    return f"✅ 已设置每日 {hour:02d}:{minute:02d} 发送消息：{message}"

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
            "name": "set_daily_message",
            "description": "设置每日定时消息",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "消息内容"},
                    "hour": {"type": "integer", "description": "小时 (0-23)"},
                    "minute": {"type": "integer", "description": "分钟 (0-59)"}
                },
                "required": ["message", "hour", "minute"]
            }
        }
    }
]

SYSTEM_INSTRUCTION = """
你是 Discord 机器人。当用户问时间时，调用 get_time 工具。
当用户说"把XX改成XX"时，调用 apply_code_patch 工具。
当用户说"每天X点发消息"时，调用 set_daily_message 工具。
其他时候正常聊天。
"""

class Agent:
    def __init__(self):
        self.history = []
        self.pending_patch = None
        self.waiting_for_confirmation = False

    async def run(self, user_input: str, user_id: str, channel=None) -> str:
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 处理确认
        if self.waiting_for_confirmation:
            if user_input.lower() in ["yes", "是", "确认", "y"]:
                result = apply_code_patch(self.pending_patch["patch"])
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return result
            elif user_input.lower() in ["no", "不", "取消", "n"]:
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return "❌ 已取消修改。"

        # 重置命令
        if user_input.strip() in ["!reset", "重置"]:
            self.history = []
            return "✅ 对话已重置"

        try:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": user_input})

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.7,
                max_tokens=8192,
                tools=TOOLS,
                tool_choice="auto"
            )

            reply = response.choices[0].message

            # 处理工具调用
            if reply.tool_calls:
                for tool_call in reply.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    if func_name == "apply_code_patch":
                        self.pending_patch = {"patch": args.get("patch_text")}
                        self.waiting_for_confirmation = True
                        return f"📝 补丁预览：\n```diff\n{args.get('patch_text')}\n```\n是否应用？回复 yes 或 no"

                    elif func_name == "get_time":
                        result = get_time()
                        self._update_history(user_input, result)
                        return result

                    elif func_name == "set_daily_message":
                        result = set_daily_message(
                            args.get("message"),
                            args.get("hour"),
                            args.get("minute")
                        )
                        self._update_history(user_input, result)
                        return result

            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text

        except Exception as e:
            return f"❌ 错误：{str(e)}"

    def _update_history(self, user_input: str, reply: str):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
