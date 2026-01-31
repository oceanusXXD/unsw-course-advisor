# test_db_async.py

import asyncio
from backend.chatbot.langgraph_agent.node.save_memory import (
    load_memory_structure_async,
    save_memory_structure_async
)

from backend.chatbot.db_manager import close_db_pool

async def test_db():
    """测试异步数据库操作"""
    try:
        print("=" * 60)
        print("测试异步数据库操作")
        print("=" * 60)
        
        # 测试加载
        print("\n1. 测试加载记忆...")
        memory = await load_memory_structure_async("test_user", "test_tab")
        print(f"[OK] Loaded memory: {memory}")
        
        # 测试保存
        print("\n2. 测试保存记忆...")
        memory["recent_conversations"].append({
            "Q": "测试问题",
            "A": "测试回答",
            "T": "2024-01-01T00:00:00"
        })
        
        await save_memory_structure_async("test_user", "test_tab", memory)
        print("[OK] Saved successfully!")
        
        # 验证保存
        print("\n3. 验证保存结果...")
        memory2 = await load_memory_structure_async("test_user", "test_tab")
        if memory2["recent_conversations"]:
            print(f"[OK] 验证成功: 找到 {len(memory2['recent_conversations'])} 条对话")
        else:
            print("[WARN] 未找到保存的对话")
        
    except Exception as e:
        print(f"[ERR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # [OK] 确保关闭连接池
        print("\n正在关闭连接池...")
        await close_db_pool()
        print("[OK] 连接池已关闭")

async def main():
    """主函数"""
    await test_db()
    
    # [OK] 给事件循环一点时间清理
    await asyncio.sleep(0.1)

if __name__ == "__main__":
    # [OK] 使用 asyncio.run() 确保事件循环正确关闭
    asyncio.run(main())