import os
import hashlib
import numpy as np
import pinecone
import requests

# Pinecone 配置
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east4-gcp")

MEMORY_INDEX = "discord-memories"
KNOWLEDGE_INDEX = "discord-knowledge"

# 初始化 Pinecone
if PINECONE_API_KEY:
    pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
    
    # 创建记忆索引
    if MEMORY_INDEX not in pc.list_indexes().names():
        pc.create_index(
            name=MEMORY_INDEX,
            dimension=384,  # 用较小的维度，避免 embedding 失败
            metric="cosine",
            spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
        )
    memory_index = pc.Index(MEMORY_INDEX)
    
    # 创建知识库索引
    if KNOWLEDGE_INDEX not in pc.list_indexes().names():
        pc.create_index(
            name=KNOWLEDGE_INDEX,
            dimension=384,
            metric="cosine",
            spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
        )
    knowledge_index = pc.Index(KNOWLEDGE_INDEX)
    
    print("✅ Pinecone 向量存储已配置")
else:
    memory_index = None
    knowledge_index = None
    print("⚠️ Pinecone 未配置")

def get_embedding(text: str) -> list:
    """获取文本的 embedding（返回浮点数列表）"""
    # 尝试用 Groq embedding
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/embeddings",
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
            json={"model": "text-embedding-3-small", "input": text},
            timeout=10
        )
        if response.status_code == 200:
            emb = response.json()["data"][0]["embedding"]
            # 确保所有值都是 float
            return [float(x) for x in emb]
    except Exception as e:
        print(f"Embedding API 失败: {e}")
    
    # 降级：生成伪 embedding（确保是 float）
    hash_val = hashlib.md5(text.encode()).hexdigest()
    # 生成 384 维的伪向量（每个值在 0-1 之间）
    emb = []
    for i in range(0, 384):
        val = int(hash_val[i % len(hash_val)], 16) / 16.0 if i < len(hash_val) else (i % 100) / 100.0
        emb.append(float(val))
    
    # 归一化
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = [float(x / norm) for x in emb]
    
    return emb[:384]

# ========== 记忆功能 ==========
def save_memory(user_id: str, text: str, metadata: dict = None):
    if not memory_index:
        return
    try:
        memory_id = f"{user_id}_{hashlib.md5(text.encode()).hexdigest()[:16]}"
        embedding = get_embedding(text)
        memory_index.upsert(vectors=[{
            "id": memory_id,
            "values": embedding,
            "metadata": metadata or {"text": text, "user_id": user_id}
        }])
    except Exception as e:
        print(f"保存记忆失败: {e}")

def search_memory(user_id: str, query: str, top_k: int = 3) -> list:
    if not memory_index:
        return []
    try:
        query_embedding = get_embedding(query)
        results = memory_index.query(
            vector=query_embedding,
            top_k=top_k,
            filter={"user_id": user_id},
            include_metadata=True
        )
        memories = []
        for match in results.matches:
            if match.metadata and 'text' in match.metadata:
                memories.append(match.metadata['text'])
        return memories
    except Exception as e:
        print(f"搜索记忆失败: {e}")
        return []

# ========== 知识库功能 ==========
def add_knowledge(text: str, metadata: dict = None):
    if not knowledge_index:
        return
    try:
        doc_id = hashlib.md5(text.encode()).hexdigest()[:16]
        embedding = get_embedding(text)
        knowledge_index.upsert(vectors=[{
            "id": doc_id,
            "values": embedding,
            "metadata": metadata or {"text": text}
        }])
    except Exception as e:
        print(f"添加知识失败: {e}")

def search_knowledge(query: str, top_k: int = 3) -> list:
    if not knowledge_index:
        return []
    try:
        query_embedding = get_embedding(query)
        results = knowledge_index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        docs = []
        for match in results.matches:
            if match.metadata and 'text' in match.metadata:
                docs.append(match.metadata['text'])
        return docs
    except Exception as e:
        print(f"搜索知识失败: {e}")
        return []

def init_knowledge():
    """初始化知识库"""
    if not knowledge_index:
        return
    
    try:
        stats = knowledge_index.describe_index_stats()
        if stats.total_vector_count > 0:
            print("知识库已有数据，跳过初始化")
            return
    except:
        pass
    
    docs = [
        "机器人名称：Gemini Bot，功能包括查询时间、联网搜索、读取文件、修改代码、定时提醒",
        "可用模型：gpt（智商最高、速度最快）、kimi（中文最好）、deepseek（推理强）、qwen（中文强）",
        "使用方法：私聊直接发消息，服务器里 @机器人 发消息，用 /model 切换模型",
        "斜杠命令：/model 切换模型，/reset 重置对话，/help 查看帮助",
        "功能示例：'现在几点'查时间、'搜索 Python'联网搜索、'读取 bot.py'读文件、'把命令前缀改成 $'改代码"
    ]
    for doc in docs:
        add_knowledge(doc)
    print("✅ 知识库初始化完成")
