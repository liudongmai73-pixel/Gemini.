import os
import json
from cerebras.cloud.sdk import Cerebras
import google.generativeai as genai
from groq import Groq
from git_manager import GitManager

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
    from datetime import datetime
    return f"🕐 当前时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}"

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
            "description": "获取当前时间。只有当用户明确询问时间时才调用。",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

SYSTEM_INSTRUCTION = """
你是 Discord 机器人。你的职责：

1. **聊天**：正常对话，友好回复。用户说"你好"时，问候即可，不要调用任何工具。
2. **查询时间**：只有用户明确说"现在几点"、"时间"、"几点了"时，才调用 get_time。
3. **修改代码**：只有用户明确说"改代码"、"修改"、"把XX改成XX"时，才调用 apply_code_patch。

**重要**：
- 不要主动调用任何工具
- 不要猜测用户意图
- 保持对话自然

现在开始！
"""

# ========== Agent 类 ==========
class Agent:
    def __init__(self):
        self.history = []
        self.pending_patch = None
        self.waiting_for_confirmation = False
        
        # 初始化各个 API
        self.cerebras_client = None
        self.gemini_client = None
        self.groq_client = None
        
        # Cerebras（最聪明，首选）
        if os.getenv("CEREBRAS_API_KEY"):
            try:
                self.cerebras_client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))
                self.cerebras_model = "llama-3.3-70b"
                print("✅ Cerebras 已配置")
            except Exception as e:
                print(f"⚠️ Cerebras 配置失败: {e}")
        
        # Gemini（次选）
        if os.getenv("GOOGLE_API_KEY"):
            try:
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
                print("✅ Gemini 已配置")
            except Exception as e:
                print(f"⚠️ Gemini 配置失败: {e}")
        
        # Groq（保底）
        if os.getenv("GROQ_API_KEY"):
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
                print("✅ Groq 已配置")
            except Exception as e:
                print(f"⚠️ Groq 配置失败: {e}")
        
        # 按智商排序的调用顺序
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

    async def run(self, user_input: str, user_id: str, channel=None) -> str:
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 处理确认
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

        # 重置命令
        if user_input.strip() in ["!reset", "重置", "清除历史"]:
            self.history = []
            self.waiting_for_confirmation = False
            self.pending_patch = None
            return "✅ 对话已重置，历史已清空"

        # 按顺序尝试各个 API
        for provider in self.providers:
            try:
                if provider == "cerebras":
                    result = await self._use_cerebras(user_input)
                elif provider == "gemini":
                    result = await self._use_gemini(user_input)
                elif provider == "groq":
                    result = await self._use_groq(user_input)
                else:
                    continue
                
                if result:
                    return result
                    
            except Exception as e:
                print(f"⚠️ {provider} 失败: {e}")
                continue
        
        return "❌ 所有 API 都失败了，请稍后再试。"

    async def _use_cerebras(self, user_input: str) -> str:
        """使用 Cerebras API"""
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
            
            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text
            
        except Exception as e:
            print(f"Cerebras 错误: {e}")
            raise

    async def _use_gemini(self, user_input: str) -> str:
        """使用 Gemini API"""
        try:
            model = genai.GenerativeModel(
                self.gemini_model,
                system_instruction=SYSTEM_INSTRUCTION
            )
            chat = model.start_chat(history=self.history)
            response = chat.send_message(user_input)
            reply = response.text
            
            # 简单检测补丁
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

    async def _use_groq(self, user_input: str) -> str:
        """使用 Groq API"""
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
            
            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text
            
        except Exception as e:
            print(f"Groq 错误: {e}")
            raise

    def _update_history(self, user_input: str, reply: str):
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
