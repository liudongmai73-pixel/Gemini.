import os
import json
from typing import List, Dict, Any
import google.genai as genai
from git_manager import GitManager

# 配置 Gemini 客户端
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# 定义工具函数（供 Gemini 调用）
def apply_code_patch(patch_text: str, commit_message: str = "Self-modify") -> str:
    """
    应用代码补丁并推送至 Git 仓库。
    参数:
        patch_text: 补丁内容（统一 diff 格式）
        commit_message: 提交信息
    """
    gm = GitManager(repo_path=os.getcwd())
    success = gm.apply_patch(patch_text, commit_message)
    if success:
        return "✅ 代码已修改并推送，Railway 将自动重新部署。"
    else:
        return "❌ 修改失败，请检查补丁格式。"

# 工具声明（供 Gemini 识别）
TOOLS = [
    {
        "name": "apply_code_patch",
        "description": "应用代码补丁并推送至 Git 仓库。",
        "parameters": {
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
    }
]

# 系统指令
SYSTEM_INSTRUCTION = """
你是一个 Discord 机器人，可以管理自己的代码。当用户要求修改代码（例如改配置、新增功能、修复 bug）时，你应该：
1. 分析当前代码文件（你可以通过读取 bot.py、agent.py 等文件来了解内容，但在此版本中暂未实现文件读取，你只能根据上下文生成补丁）
2. 生成所需的补丁（统一 diff 格式）
3. 调用 apply_code_patch 工具来应用补丁
在调用前，向用户展示补丁内容并等待确认。只有在用户明确同意后才执行。
如果用户只是普通对话，则正常回复。
"""

class Agent:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []  # 存储对话历史（包括工具调用）
        # 配置生成参数，允许函数调用
        self.config = {
            "system_instruction": SYSTEM_INSTRUCTION,
            "tools": TOOLS,
            "tool_config": {"function_calling_config": "AUTO"},
            "temperature": 0.7,
            "max_output_tokens": 8192,
        }

    async def run(self, user_input: str, user_id: str) -> str:
        """处理用户输入，返回回复文本"""
        # 权限检查
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 将用户输入加入历史
        self.history.append({"role": "user", "parts": [user_input]})

        # 调用 Gemini 生成响应（支持工具调用）
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=self.history,
            config=self.config
        )

        # 处理可能的函数调用
        if response.function_calls:
            # 当前仅支持单个函数调用，若需多个可扩展
            fc = response.function_calls[0]
            if fc.name == "apply_code_patch":
                # 解析参数
                args = {k: v for k, v in fc.args.items()}
                # 实际调用函数
                result = apply_code_patch(**args)
                # 将函数调用结果添加回历史（以 'model' 角色记录工具调用，然后添加 'function' 响应）
                self.history.append({"role": "model", "parts": [{"function_call": fc}]})
                self.history.append({"role": "function", "parts": [{"function_response": {"name": fc.name, "response": result}}]})
                # 再次调用模型，让它生成最终回复（基于工具结果）
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
            # 无函数调用，直接返回文本
            reply = response.text
            self.history.append({"role": "model", "parts": [reply]})
            return reply
