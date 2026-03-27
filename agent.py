import os
import json
import asyncio
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from git_manager import GitManager

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    gm = GitManager(repo_path=os.getcwd())
    success = gm.apply_patch(patch_text, commit_message)
    if success:
        return "✅ 代码已修改并推送，Railway 将自动重新部署。"
    else:
        return "❌ 修改失败，请检查补丁格式。"

apply_patch_decl = FunctionDeclaration(
    name="apply_code_patch",
    description="应用代码补丁并推送至 Git，实现自我修改。",
    parameters={
        "type": "object",
        "properties": {
            "patch_text": {
                "type": "string",
                "description": "统一 diff 格式的补丁内容"
            },
            "commit_message": {
                "type": "string",
                "description": "提交信息（默认 'Self-modify'）"
            }
        },
        "required": ["patch_text"]
    }
)

tool = Tool(function_declarations=[apply_patch_decl])

SYSTEM_PROMPT = """
你是一个 Discord 机器人，可以管理自己的代码。当用户要求修改代码（例如改配置、新增功能、修复 bug）时，你应该：
1. 分析当前代码文件（可以读取 bot.py、agent.py 等）
2. 生成所需的补丁（统一 diff 格式）
3. 调用 apply_code_patch 工具来应用补丁
在调用前，向用户展示补丁内容并等待确认。只有在用户明确同意后才执行。
如果用户只是普通对话，则正常回复。
"""

class Agent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            tools=[tool],
            tool_config={"function_calling_config": "AUTO"}
        )
        self.chat = None

    async def run(self, user_input: str, user_id: str):
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        if self.chat is None:
            self.chat = self.model.start_chat(history=[])

        response = self.chat.send_message(user_input)

        if response.candidates[0].content.parts[0].function_call:
            fc = response.candidates[0].content.parts[0].function_call
            if fc.name == "apply_code_patch":
                args = {k: v for k, v in fc.args.items()}
                result = apply_code_patch(**args)
                # 将结果返回给模型
                self.chat.send_message(
                    genai.protos.Content(
                        role="function",
                        parts=[genai.protos.Part(function_response=genai.protos.FunctionResponse(
                            name=fc.name,
                            response={"result": result}
                        ))]
                    )
                )
                final = self.chat.send_message("继续")
                return final.text
        else:
            return response.text
