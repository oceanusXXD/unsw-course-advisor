# unsw-course-advisor\backend\test\test_activation.py
import os
import sys
from pathlib import Path
import django

# 调试：打印当前路径和项目根目录
print(f"当前脚本路径: {Path(__file__).absolute()}")
project_root = Path(__file__).parent.parent  # backend/test/.. => backend/
print(f"项目根目录: {project_root.absolute()}")

# 将项目根目录添加到 Python 路径
sys.path.append(str(project_root))

# 设置 Django 环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")  # 注意是 'backend.settings' 不是 'unsw-course-advisor.settings'
django.setup()

# 现在可以安全导入依赖 Django 的模块
from chatbot.langgraph_agent.tools.crypto import node_crypto

# 测试代码
state = {"data": {"message": "Hello, secure world!", "value": 123}}
res = node_crypto(state)
print(res)