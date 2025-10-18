# unsw-course-advisor\backend\test\generate_license_and_save.py
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
from chatbot.langgraph_agent.tools.crypto import activate_license
from decrypto_local import activate_license_from_server
# 你可以改 user_id / device_id
USER_ID = "testuser"
DEVICE_ID = "device-test-01"

# 1) 在服务器端生成许可证（返回 license_key + user_key）
license_info = activate_license(USER_ID, DEVICE_ID)
print("服务器返回：", license_info)

# 2) 将 license 写到客户端本地（调用客户端函数）
activate_license_from_server(
    license_key=license_info["license_key"],
    user_key=license_info["user_key"],
    user_id=USER_ID
)

# 直接打印全局变量
from decrypto_local import LICENSE_FILE
print(f"✅ 许可证已保存到: {LICENSE_FILE}")


