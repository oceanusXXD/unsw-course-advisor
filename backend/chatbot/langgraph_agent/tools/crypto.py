# crypto.py
import os
import json
import uuid
import base64
from typing import Dict, Any
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from django.conf import settings
from dotenv import load_dotenv, set_key

# 1️⃣ 载入 .env 环境变量
env_path = os.path.join(settings.BASE_DIR, ".RSA.env")
load_dotenv(env_path)

# 2️⃣ 检查是否已有密钥对，否则自动生成
PRIVATE_KEY_FILE = os.path.join(settings.BASE_DIR, "private.pem")
PUBLIC_KEY_FILE = os.path.join(settings.BASE_DIR, "public.pem")

if not (os.path.exists(PRIVATE_KEY_FILE) and os.path.exists(PUBLIC_KEY_FILE)):
    print("⚙️ 未检测到RSA密钥对，正在生成中...")
    key = RSA.generate(2048)

    private_key = key.export_key()
    public_key = key.publickey().export_key()

    with open(PRIVATE_KEY_FILE, "wb") as f:
        f.write(private_key)
    with open(PUBLIC_KEY_FILE, "wb") as f:
        f.write(public_key)

    print("✅ 已生成RSA密钥对")

    # 保存到 .env（方便其它服务读取）
    set_key(env_path, "RSA_PUBLIC_KEY_PATH", PUBLIC_KEY_FILE)
    set_key(env_path, "RSA_PRIVATE_KEY_PATH", PRIVATE_KEY_FILE)
else:
    print("🔑 已检测到RSA密钥对，跳过生成")

# 3️⃣ 加密主函数
def node_crypto(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    混合加密方案（RSA + AES-GCM）
    从 state['data'] 读取内容，加密后保存文件，返回下载 URL
    """
    print("🔐 [node_crypto] state keys:", list(state.keys()))

    # 1. 准备数据
    data = state.get("data")
    if data is None:
        return {"error": "Missing 'data' field for encryption"}

    if isinstance(data, (dict, list)):
        data_str = json.dumps(data, ensure_ascii=False)
    else:
        data_str = str(data)

    plaintext = data_str.encode("utf-8")

    # 2. 加载RSA公钥
    with open(PUBLIC_KEY_FILE, "rb") as f:
        public_key = RSA.import_key(f.read())

    # 3. 生成随机AES密钥并加密数据
    aes_key = get_random_bytes(32)  # AES-256
    nonce = get_random_bytes(12)
    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher_aes.encrypt_and_digest(plaintext)

    # 4. 用RSA公钥加密AES密钥
    cipher_rsa = PKCS1_OAEP.new(public_key)
    enc_aes_key = cipher_rsa.encrypt(aes_key)

    # 5. 组合最终加密结果
    enc_data = {
        "key": base64.b64encode(enc_aes_key).decode("utf-8"),
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "tag": base64.b64encode(tag).decode("utf-8"),
        "data": base64.b64encode(ciphertext).decode("utf-8"),
    }

    # 6. 保存文件
    enc_dir = os.path.join(settings.MEDIA_ROOT, "encrypted")
    os.makedirs(enc_dir, exist_ok=True)

    filename = f"enc_{uuid.uuid4().hex[:8]}.json"
    file_path = os.path.join(enc_dir, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(enc_data, f, ensure_ascii=False, indent=2)

    download_url = f"{settings.MEDIA_URL.rstrip('/')}/encrypted/{filename}"
    print("✅ [node_crypto] 加密文件已保存:", file_path)

    return {"url": download_url}
