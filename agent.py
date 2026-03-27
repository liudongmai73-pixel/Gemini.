import os
import google.generativeai as genai
from groq import Groq
from together import Together
from git_manager import GitManager

class Agent:
    def __init__(self):
        self.history = []
        self.current_provider = None
        self.providers = []
        
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
            
            # 如果成功返回，更新当前 provider
            if reply and not reply.startswith("❌"):
                self.current_provider = provider
                return reply
            
            print(f"⚠️ {provider} 失败，尝试下一个...")
        
        return "❌ 所有 API 都失败了，请稍后再试。"

    async def _use_gemini(self, user_input: str) -> str:
        """使用 Gemini API"""
        try:
            model = genai.GenerativeModel(
                self.gemini_model,
                system_instruction="你是一个 Discord 机器人，可以回答问题、帮助用户。请用中文回复，保持友好、有帮助的语气。"
            )
            chat = model.start_chat(history=self.history)
            response = chat.send_message(user_input)
            reply = response.text
            
            self._update_history(user_input, reply)
            return reply
            
        except Exception as e:
            error_msg = str(e)
            print(f"Gemini 错误: {error_msg}")
            return f"❌ Gemini 失败: {error_msg[:100]}"

    async def _use_groq(self, user_input: str) -> str:
        """使用 Groq API"""
        try:
            # 构建消息
            messages = []
            for msg in self.history:
                messages.append({"role": msg["role"], "content": msg["parts"][0]})
            messages.append({"role": "user", "content": user_input})
            
            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                temperature=0.7,
                max_tokens=8192
            )
            
            reply = response.choices[0].message.content
            
            self._update_history(user_input, reply)
            return reply
            
        except Exception as e:
            error_msg = str(e)
            print(f"Groq 错误: {error_msg}")
            return f"❌ Groq 失败: {error_msg[:100]}"

    async def _use_together(self, user_input: str) -> str:
        """使用 Together API"""
        try:
            # 构建消息
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
            error_msg = str(e)
            print(f"Together 错误: {error_msg}")
            return f"❌ Together 失败: {error_msg[:100]}"

    def _update_history(self, user_input: str, reply: str):
        """更新对话历史"""
        self.history.append({"role": "user", "parts": [user_input]})
        self.history.append({"role": "model", "parts": [reply]})
