import os
import google.generativeai as genai
from git_manager import GitManager

# 配置 Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

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

# 工具声明（Gemini 函数调用格式）
TOOLS = [
    {
        "name": "apply_code_patch",
        "description": "应用代码补丁并推送至 Git 仓库，实现自我修改。",
        "parameters": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": "统一 diff 格式的补丁内容。例如：--- a/bot.py\\n+++ b/bot.py\\n@@ -5,7 +5,7 @@\\n-bot = commands.Bot(command_prefix='!')\\n+bot = commands.Bot(command_prefix='$')"
                },
                "commit_message": {
                    "type": "string",
                    "description": "提交信息，描述这次修改的内容"
                }
            },
            "required": ["patch_text"]
        }
    }
]

SYSTEM_INSTRUCTION = """
你是一个 Discord 机器人，可以管理自己的代码。你的能力：

1. **普通对话**：回答用户问题，帮助用户。
2. **自我修改代码**：当用户要求修改代码时，你需要：
   - 分析用户需求（例如改配置、新增功能、修复bug）
   - 读取相关代码文件（你可以通过分析用户提供的上下文或之前的信息）
   - 生成统一 diff 格式的补丁
   - 调用 apply_code_patch 工具来应用补丁

**重要规则**：
- 在调用 apply_code_patch 之前，必须先向用户展示补丁内容，并询问确认
- 只有在用户明确回复 "yes"、"是"、"确认"、"同意" 等确认词后，才能调用工具
- 如果用户拒绝或没有确认，不要调用工具
- 如果用户只是普通对话，正常回复即可

**补丁格式示例**：
--- a/bot.py
+++ b/bot.py
@@ -5,7 +5,7 @@
-bot = commands.Bot(command_prefix='!')
+bot = commands.Bot(command_prefix='$')

请用中文回复，保持友好、有帮助的语气。
"""

class Agent:
    def __init__(self):
        self.history = []
        self.model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=TOOLS,
            tool_config={"function_calling_config": "AUTO"}
        )
        self.chat = None

    async def run(self, user_input: str, user_id: str) -> str:
        # 权限检查
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        try:
            # 初始化或获取聊天会话
            if self.chat is None:
                self.chat = self.model.start_chat(history=[])

            # 发送用户消息
            response = self.chat.send_message(user_input)

            # 检查是否有函数调用
            if response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                
                # 如果是函数调用
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    if fc.name == "apply_code_patch":
                        # 解析参数
                        args = {}
                        for key, value in fc.args.items():
                            args[key] = value
                        
                        # 执行函数
                        result = apply_code_patch(**args)
                        
                        # 将函数调用结果返回给模型
                        response = self.chat.send_message(
                            f"函数执行结果：{result}",
                            generation_config={"tools": TOOLS}
                        )
                        reply = response.text
                        return reply
                    else:
                        return f"未知函数调用: {fc.name}"
                else:
                    # 普通文本回复
                    return response.text
            else:
                return "抱歉，我无法处理这个请求。"

        except Exception as e:
            error_msg = str(e)
            print(f"错误: {error_msg}")
            
            if "quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                return "❌ Gemini API 配额暂时不可用，请稍后再试。如果是第一次使用，可能需要等待几分钟让 API Key 生效。"
            
            if "function_calling" in error_msg.lower():
                return "⚠️ 函数调用配置错误，但基础对话功能正常。你可以先测试普通对话。"
            
            return f"❌ 错误：{error_msg[:200]}"
