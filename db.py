import sqlite3
import json
import os

DB_PATH = "/data/conversations.db"

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 对话历史表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            user_id TEXT PRIMARY KEY,
            history TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 用户设置表（模型偏好等）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            preferred_model TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")

def save_history(user_id: str, history: list):
    """保存对话历史"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO conversations (user_id, history, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, json.dumps(history, ensure_ascii=False)))
    conn.commit()
    conn.close()

def load_history(user_id: str) -> list:
    """加载对话历史"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT history FROM conversations WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['history']:
        return json.loads(row['history'])
    return []

def save_model_preference(user_id: str, model: str):
    """保存用户偏好的模型"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_settings (user_id, preferred_model, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, model))
    conn.commit()
    conn.close()

def load_model_preference(user_id: str) -> str:
    """加载用户偏好的模型"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT preferred_model FROM user_settings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['preferred_model']:
        return row['preferred_model']
    return None
