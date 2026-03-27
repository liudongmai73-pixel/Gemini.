import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from agent import Agent

# 加载环境变量
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 创建 bot
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
agent = Agent()

@bot.event
async def on_ready():
    print(f"✅ 机器人已登录！")
    print(f"Bot 名称: {bot.user}")
    print(f"Bot ID: {bot.user.id}")

@bot.event
async def on_message(message):
    # 忽略自己的消息
    if message.author == bot.user:
        return
    
    # 处理命令
    await bot.process_commands(message)
    
    # 普通消息交给 Agent 处理
    if not message.content.startswith("!"):
        async with message.channel.typing():
            result = await agent.run(message.content, str(message.author.id))
            if result:
                # 如果消息太长，分段发送
                for chunk in [result[i:i+2000] for i in range(0, len(result), 2000)]:
                    await message.channel.send(chunk)

@bot.command()
async def ping(ctx):
    """测试机器人是否在线"""
    await ctx.send(f"🏓 Pong! 延迟: {round(bot.latency * 1000)}ms")

@bot.command()
async def eval(ctx, *, code: str):
    """执行 Python 代码（仅限授权用户）"""
    authorized = os.getenv("AUTHORIZED_USERS", "").split(",")
    if str(ctx.author.id) not in authorized:
        return await ctx.send("❌ 无权限")
    try:
        exec_globals = {}
        exec(code, exec_globals)
        result = exec_globals.get("result", "无返回值")
        await ctx.send(f"✅ 执行成功\n```\n{result}\n```")
    except Exception as e:
        await ctx.send(f"❌ 错误：{e}")

# 运行 bot
if __name__ == "__main__":
    print("正在启动机器人...")
    bot.run(TOKEN)
