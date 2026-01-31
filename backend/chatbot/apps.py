# backend/chatbot/apps.py

import threading
import traceback
import os
from django.apps import AppConfig
import asyncio

class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'

    def ready(self):
        """
        Django 启动时初始化：
        1. 加载混合检索模块（单例模式，只初始化一次）
        2. 预编译 LangGraph（复用已加载的检索模块）
        
        关键：先加载检索模块，再编译图，避免重复初始化
        """
        # 只在主进程运行（避免 reload 时重复）
        if os.environ.get("RUN_MAIN") == "true":
            print("[SKIP] [Chatbot.ready] Reload 子进程检测到，跳过初始化。")
            return

        def _init_in_background():
            """后台初始化：先加载模块，再编译图"""
            try:
                # === 步骤 1：加载混合检索模块 ===
                print("[START] [Chatbot.ready] Step 1: 加载混合检索模块...")
                from chatbot.langgraph_agent import parallel_search_and_rerank
                print("[OK] [Chatbot.ready] Hybrid Search 模块已加载")
                print("   -> VectorSearch, Reranker, KnowledgeGraph 已就绪")

                # === 步骤 2：预编译 LangGraph ===
                print("\n[BUILD] [Chatbot.ready] Step 2: 预编译 LangGraph...")
                from chatbot.langgraph_agent.main_graph import warmup_graph
                
                graph = warmup_graph()
                if graph:
                    print("[OK] [Chatbot.ready] LangGraph 预编译成功")
                    print("   -> 所有节点已加载（复用已初始化的检索模块）")
                else:
                    print("[WARN] [Chatbot.ready] LangGraph 预编译失败（将在首次请求时编译）")

                print("\n[DONE] [Chatbot.ready] 初始化完成，服务已就绪！\n")
                import atexit
                from .db_manager import close_db_pool
                
                def cleanup():
                    """清理函数"""
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(close_db_pool())
                        loop.close()
                    except Exception:
                        pass
                    
                atexit.register(cleanup)
            except Exception as e:
                print(f"[ERR] [Chatbot.ready] 初始化失败: {e}")
                traceback.print_exc()

        # 在后台线程执行，避免阻塞 Django 启动
        print("[INIT] [Chatbot.ready] 开始后台初始化...")
        threading.Thread(target=_init_in_background, daemon=True).start()