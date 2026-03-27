import os
import google.genai as genai
from google.genai import types

# 配置 Gemini 客户端
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

SYSTEM_INSTRUCTION = """
你是一个 Discord 机器人，可以回答问题、帮助用户。请用中文回复，保持友好、有帮助的语气。
"""

class Agent:
    def __init__(self):
        self.history = []
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
            max_output_tokens=8192,
        )

    async def run(self, user_input: str, user_id: str) -> str:
        # 权限检查
        authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
        if user_id not in authorized:
            return "❌ 你没有权限使用此机器人。"

        # 添加用户消息到历史
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_input)]))

        try:
            # 调用 Gemini
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=self.history,
                config=self.config
            )
            
            reply = response.text
            self.history.append(types.Content(role="model", parts=[types.Part(text=reply)]))
            return reply
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error: {error_msg}")
            return f"❌ 出错了：{error_msg[:200]}"
