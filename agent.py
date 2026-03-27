import os
import json
from groq import Groq
import google.generativeai as genai
from together import Together
from git_manager import GitManager

# 定义工具函数（供 AI 调用）
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

# 工具定义（统一格式）
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "apply_code_patch",
        "description": "应用代码补丁并推送至 Git 仓库，实现自我修改。",
        "parameters": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": "统一 diff 格式的补丁内容"
                },
                "commit_message": {
                    "type": "string",
                    "description": "提交信息，描述这次修改的内容"
                }
            },
            "required": ["patch_text"]
        }
    }
}

SYSTEM_INSTRUCTION = """
你是一个 Discord 机器人，可以管理自己的代码。你的能力：

1. **普通对话**：回答用户问题，帮助用户。
2. **自我修改代码**：当用户要求修改代码时，你需要：
   - 分析用户需求
   - 生成统一 diff 格式的补丁
   - 向用户展示补丁内容，并询问确认
   - 只有在用户明确回复 "yes"、"是"、"确认" 后，才能调用 apply_code_patch 工具

**重要规则**：
- 绝对不能在未经用户确认的情况下调用 apply_code_patch
- 必须先展示补丁，等待用户确认
- 如果用户没有确认，不要执行任何修改

请用中文回复，保持友好、有帮助的语气。
"""

class Agent:
    def __init__(self):
        self.history = []
        self.providers = []
        self.pending_patch = None  # 待确认的补丁
        self.pending_message = None  # 待确认的消息
        self.waiting_for_confirmation = False  # 是否等待确认
        
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
            raise Exception("❌ 没有可用的 API！请设置至少一个 API Key")
        
        self.current_provider = self.providers[0]
        print(f"🚀 默认使用: {self.current_provider}")

    async def run(self, user_input: str, user_id: str) -> str:
        # 权限检查
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 检查是否是确认消息
        if self.waiting_for_confirmation:
            if user_input.lower() in ["yes", "是", "确认", "同意", "y"]:
                # 执行补丁
                result = apply_code_patch(self.pending_patch["patch"], self.pending_patch["message"])
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return result
            elif user_input.lower() in ["no", "不", "取消", "n"]:
                self.waiting_for_confirmation = False
                self.pending_patch = None
                return "❌ 已取消修改。"
            else:
                return "请回复 yes 确认修改，或 no 取消。"

        # 尝试所有 provider
        for provider in self.providers:
            if provider == "gemini":
                reply = await self._use_gemini(user_input)
            elif provider == "groq":
                reply = await self._use_groq(user_input)
            elif provider == "together":
                reply = await self._use_together(user_input)
            else:
                continue
            
            # 如果成功返回
            if reply:
                self.current_provider = provider
                return reply
            
            print(f"⚠️ {provider} 失败，尝试下一个...")
        
        return "❌ 所有 API 都失败了，请稍后再试。"

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
            
            self._update_history(user_input, reply)
            return reply
            
        except Exception as e:
            print(f"Gemini 错误: {e}")
            return None

    async def _use_groq(self, user_input: str) -> str:
        """使用 Groq API"""
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
                tools=[TOOL_DEFINITION],
                tool_choice="auto"
            )
            
            reply = response.choices[0].message
            
            # 检查是否有工具调用
            if reply.tool_calls:
                for tool_call in reply.tool_calls:
                    if tool_call.function.name == "apply_code_patch":
                        # 不直接执行，先保存待确认
                        args = json.loads(tool_call.function.arguments)
                        patch_text = args.get("patch_text", "")
                        commit_msg = args.get("commit_message", "Self-modify")
                        
                        # 保存待确认的补丁
                        self.pending_patch = {"patch": patch_text, "message": commit_msg}
                        self.waiting_for_confirmation = True
                        
                        # 返回补丁预览，请求确认
                        return f"📝 检测到修改请求，补丁如下：\n```diff\n{patch_text}\n```\n\n是否应用这个修改？请回复 yes 或 no。"
            
            reply_text = reply.content
            self._update_history(user_input, reply_text)
            return reply_text
            
        except Exception as e:
            print(f"Groq 错误: {e}")
            return None

    async def _use_together(self, user_input: str) -> str:
        """使用 Together API"""
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
            
            # 检查是否包含补丁
            if "--- a/" in reply and "+++ b/" in reply and "@@" in reply:
                patch = self._extract_patch(reply)
                if patch:
                    self.pending_patch = {"patch": patch, "message": "Self-modify"}
                    self.waiting_for_confirmation = True
                    return reply + "\n\n是否应用这个修改？请回复 yes 或 no。"
            
            self._update_history(user_input, reply)
            return reply
            
        except Exception as e:
            print(f"Together 错误: {e}")
            return None

    def _extract_patch(self, text: str) -> str:
        """从回复中提取补丁内容"""
        lines = text.split('\n')
        patch_lines = []
        in_patch = False
        
        for line in lines:
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                in_patch = True
                patch_lines.append(line)
            elif in_patch and (line.startswith('@@') or line.startswith('+') or line.startswith('-') or line.startswith(' ')):
                patch_lines.append(line)
            elif in_patch and line.strip() == '':
                continue
            elif in_patch and not line.startswith(('@@', '+', '-', ' ')):
                break
        
        if patch_lines:
            return '\n'.join(patch_lines)
        return None

    def _update_history(self, user_input: str, reply: str):
        """更新对话历史"""
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "assistant", "parts": [reply]})
