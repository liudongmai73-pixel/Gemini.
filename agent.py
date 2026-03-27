import os
import google.genai as genai
from git_manager import GitManager

# 配置 Gemini 客户端
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")  # 推荐使用稳定版

# 定义工具函数
def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    gm = GitManager(repo_path=os.getcwd())
    success = gm.apply_patch(patch_text, commit_message)
    if success:
        return "✅ 代码已修改并推送，Railway 将自动重新部署。"
    else:
        return "❌ 修改失败，请检查补丁格式。"

# 工具声明
TOOLS = [
    {
        "name": "apply_code_patch",
        "description": "应用代码补丁并推送至 Git 仓库。",
        "parameters": {
            "type": "object",
            "properties": {
                "patch_text": {"type": "string", "description": "统一 diff 格式的补丁内容"},
                "commit_message": {"type": "string", "description": "提交信息（默认 'Self-modify'）"}
            },
            "required": ["patch_text"]
        }
    }
]

SYSTEM_INSTRUCTION = """
你是一个 Discord 机器人，可以管理自己的代码。当用户要求修改代码时，你应该：
1. 分析代码内容（可读取文件，但当前版本未实现）
2. 生成所需的补丁（统一 diff 格式）
3. 调用 apply_code_patch 工具来应用补丁
在调用前，向用户展示补丁内容并等待确认。只有在用户明确同意后才执行。
如果用户只是普通对话，则正常回复。
"""

class Agent:
    def __init__(self):
        self.history = []
        self.config = {
            "system_instruction": SYSTEM_INSTRUCTION,
            "tools": TOOLS,
            "tool_config": {"function_calling_config": "AUTO"},
            "temperature": 0.7,
            "max_output_tokens": 8192,
        }

    async def run(self, user_input: str, user_id: str) -> str:
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        self.history.append({"role": "user", "parts": [user_input]})

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=self.history,
            config=self.config
        )

        if response.function_calls:
            fc = response.function_calls[0]
            if fc.name == "apply_code_patch":
                args = {k: v for k, v in fc.args.items()}
                result = apply_code_patch(**args)
                # 添加工具调用和结果到历史
                self.history.append({"role": "model", "parts": [{"function_call": fc}]})
                self.history.append({"role": "function", "parts": [{"function_response": {"name": fc.name, "response": result}}]})
                final_response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=self.history,
                    config=self.config
                )
                final_text = final_response.text
                self.history.append({"role": "model", "parts": [final_text]})
                return final_text
            else:
                return f"未知函数调用: {fc.name}"
        else:
            reply = response.text
            self.history.append({"role": "model", "parts": [reply]})
            return reply
