#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

def ensure_rsa_keys():
    """检查并生成RSA公私钥，如果不存在则自动生成并写入.env"""
    from Crypto.PublicKey import RSA
    from dotenv import load_dotenv, set_key

    BASE_DIR = Path(__file__).resolve().parent
    env_path = BASE_DIR / ".RSA.env"

    # 载入 .env 文件（如果存在）
    if env_path.exists():
        load_dotenv(env_path)

    public_key_path = os.getenv("RSA_PUBLIC_KEY", str(BASE_DIR / "public.pem"))
    private_key_path = os.getenv("RSA_PRIVATE_KEY", str(BASE_DIR / "private.pem"))

    # 如果密钥文件不存在，自动生成
    if not (os.path.exists(public_key_path) and os.path.exists(private_key_path)):
        print("🔑 [keygen] 检查RSA密钥...")

        key = RSA.generate(2048)
        with open(private_key_path, "wb") as f:
            f.write(key.export_key())
        with open(public_key_path, "wb") as f:
            f.write(key.publickey().export_key())

        # 如果 .env 不存在，创建它
        if not env_path.exists():
            env_path.touch()

        # 写入密钥路径
        set_key(str(env_path), "RSA_PUBLIC_KEY", public_key_path)
        set_key(str(env_path), "RSA_PRIVATE_KEY", private_key_path)

        print("✅ [keygen] 已生成新密钥对，并写入 .env")
    else:
        print("🔒 [keygen] 检测到RSA密钥已存在，跳过生成。")

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

    # ✅ 启动前自动检查/生成RSA密钥
    ensure_rsa_keys()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
