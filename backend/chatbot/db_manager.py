# backend/chatbot/db_manager.py

import os
import asyncio
import aiomysql
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import atexit
import json
import datetime
# 保留原有的 Error 类
class Error(Exception):
    """统一捕获数据库异常"""
    pass

# ===== 异步版本（改进版）=====

# 全局连接池
_ASYNC_POOL: Optional[aiomysql.Pool] = None
_POOL_LOCK = asyncio.Lock()

async def get_async_db_pool() -> aiomysql.Pool:
    """
    获取异步数据库连接池（单例模式）
    """
    global _ASYNC_POOL
    
    if _ASYNC_POOL is not None:
        return _ASYNC_POOL
    
    async with _POOL_LOCK:
        if _ASYNC_POOL is not None:
            return _ASYNC_POOL
        
        try:
            _ASYNC_POOL = await aiomysql.create_pool(
                host=os.getenv('DB_HOST', '127.0.0.1'),
                port=int(os.getenv('DB_PORT', 3306)),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', ''),
                db=os.getenv('DB_NAME', 'chatbot'),
                charset='utf8mb4',
                autocommit=False,
                minsize=1,
                maxsize=10,
                echo=False,
                cursorclass=aiomysql.DictCursor,
                # 添加连接超时设置
                connect_timeout=10,
                # 禁用警告（如果需要）
                init_command="SET sql_mode='TRADITIONAL'"
            )
            print("[OK] [DB] Async connection pool initialized")
            return _ASYNC_POOL
        except Exception as e:
            raise Error(f"异步数据库连接池创建失败: {e}")

@asynccontextmanager
async def get_async_db_connection():
    """
    异步上下文管理器，自动获取和释放连接
    """
    pool = await get_async_db_pool()
    conn = None
    cursor = None
    
    try:
        # 使用 async with 确保连接正确释放
        conn = await pool.acquire()
        cursor = await conn.cursor(aiomysql.DictCursor)
        
        try:
            yield conn, cursor
        finally:
            # 确保 cursor 关闭
            await cursor.close()
    finally:
        # 确保连接返回池中
        if conn:
            await conn.ensure_closed()
            pool.release(conn)

async def close_db_pool():
    """关闭连接池（应用关闭时调用）"""
    global _ASYNC_POOL
    if _ASYNC_POOL:
        _ASYNC_POOL.close()
        await _ASYNC_POOL.wait_closed()
        _ASYNC_POOL = None
        print("[OK] [DB] Async connection pool closed")

# 注册清理函数
def cleanup_pool_sync():
    """同步清理函数（用于程序退出时）"""
    if _ASYNC_POOL:
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.run_until_complete(close_db_pool())
        except Exception:
            pass

# 注册退出时清理
atexit.register(cleanup_pool_sync)

# ===== 保留同步版本（向后兼容）=====

import pymysql
pymysql.install_as_MySQLdb()

def get_db_connection():
    """
    [已废弃] 同步版本，仅供向后兼容
    """
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'chatbot'),
            port=int(os.getenv('DB_PORT', 3306)),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        return conn
    except Exception as e:
        raise Error(f"数据库连接失败: {e}")
    

async def load_chat_messages_from_db(
    user_id: str,
    tab_id: str,
    k: int = 10,
) -> list[dict]:
    """
    加载最近 k 条对话（按时间倒序取，返回前在内存中反转为时间正序）。
    返回格式：List[{"Q": str, "A": str, "T": iso_str, "metadata": dict}]
    """
    try:
        async with get_async_db_connection() as (conn, cursor):
            # 倒序 + LIMIT k
            await cursor.execute(
                """
                SELECT timestamp, question, answer, metadata
                FROM tab_memory
                WHERE user_id = %s AND tab_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (user_id, tab_id, int(k)),
            )
            rows = await cursor.fetchall() or []

        # 反转为时间正序
        rows.reverse()

        convs: list[dict] = []
        for r in rows:
            # metadata JSON 解析
            meta = {}
            try:
                meta = json.loads(r["metadata"]) if r.get("metadata") else {}
            except Exception:
                meta = {}

            convs.append(
                {
                    "Q": r.get("question", "") or "",
                    "A": r.get("answer", "") or "",
                    "T": (r.get("timestamp") or datetime.now()).isoformat(),
                    "metadata": meta,
                }
            )
        return convs

    except Exception as e:
        # 不抛出，避免影响主流程；返回空列表
        # 也可以根据你的日志策略打印
        return []