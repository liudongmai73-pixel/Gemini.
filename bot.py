import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from agent import Agent

# 加载环境变量
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 创建 bot，设置命令前缀（初始为 !，可以被 Agent 修改）
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
agent = Agent()

# 将 bot 实例传给 agent（用于定时任务等）
agent.set_bot(bot)

@bot.event
async def on_ready():
    """机器人启动时触发"""
    print(f"✅ 机器人已登录！")
    print(f"Bot 名称: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"已连接到 {len(bot.guilds)} 个服务器")

@bot.event
async def on_message(message):
    """收到消息时触发"""
    # 忽略自己的消息
    if message.author == bot.user:
        return
    
    # 处理命令（如 !ping）
    await bot.process_commands(message)
    
    # 普通消息（不以 ! 开头）交给 Agent 处理
    if not message.content.startswith("!"):
        async with message.channel.typing():
            try:
                result = await agent.run(
                    message.content, 
                    str(message.author.id), 
                    message.channel
                )
                if result:
                    # 如果消息太长，分段发送（Discord 限制 2000 字符）
                    for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                        await message.channel.send(chunk)
            except Exception as e:
                print(f"错误: {e}")
                await message.channel.send(f"❌ 出错了：{str(e)[:200]}")

@bot.command()
async def ping(ctx):
    """测试机器人是否在线"""
    await ctx.send(f"🏓 Pong! 延迟: {round(bot.latency * 1000)}ms")

@bot.command()
async def hello(ctx):
    """打招呼"""
    await ctx.send(f"你好 {ctx.author.name}！")

@bot.command()
async def help(ctx):
    """显示帮助信息"""
    help_text = """
**🤖 Discord Agent 帮助菜单**

**基础命令：**
`!ping` - 测试机器人延迟
`!hello` - 打招呼
`!help` - 显示此帮助

**AI 对话：**
直接发送消息（不加 ! 前缀）即可与我对话

**我支持的功能：**
- 💬 智能对话（自动切换 Gemini/Groq/Together）
- 📝 自我修改代码（说"把命令前缀改成 $"，确认后生效）
- 📁 文件管理（读、写、列、删文件）
- 🔍 联网搜索（搜索最新信息）
- 🌐 获取网页内容
- 🌤️ 天气查询
- 🕐 时间查询
- ⏰ 定时提醒

**注意**：斜杠命令（/）需要在 Discord Developer Portal 手动配置，无法通过对话添加。

有什么我可以帮你的吗？
"""
    await ctx.send(help_text)

@bot.command()
async def eval(ctx, *, code: str):
    """执行 Python 代码（仅限授权用户）"""
    authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
    if str(ctx.author.id) not in authorized:
        return await ctx.send("❌ 你没有权限使用此命令。")
    
    try:
        # 创建安全的执行环境
        exec_globals = {
            "bot": bot,
            "ctx": ctx,
            "discord": discord,
            "commands": commands,
            "os": os,
            "requests": __import__("requests"),
            "json": __import__("json"),
        }
        exec(code, exec_globals)
        result = exec_globals.get("result", "无返回值")
        await ctx.send(f"✅ 执行成功\n```python\n{result}\n```")
    except Exception as e:
        await ctx.send(f"❌ 错误：{e}")

# 动态更新命令前缀的功能
def update_prefix(bot_instance, new_prefix):
    """更新 bot 的命令前缀（供 Agent 调用）"""
    bot_instance.command_prefix = new_prefix
    print(f"命令前缀已更新为: {new_prefix}")

# 运行 bot
if __name__ == "__main__":
    print("正在启动机器人...")
    bot.run(TOKEN)
