# crypto.py  — replace your existing chatbot.langgraph_agent.tools.crypto with this content
import os
import json
import uuid
import base64
import hashlib
from typing import Dict, Any
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from dotenv import load_dotenv

load_dotenv()

# -------------------- MEDIA 根设置（兼容无 Django 环境） --------------------
MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(os.getcwd(), "media"))
MEDIA_URL = os.getenv("MEDIA_URL", "http://localhost/media/")
os.makedirs(os.path.join(MEDIA_ROOT, "encrypted"), exist_ok=True)

# -------------------- 存储文件路径 --------------------
STORAGE_DIR = os.path.join(MEDIA_ROOT, "license_store")
os.makedirs(STORAGE_DIR, exist_ok=True)
USER_STORE_FILE = os.path.join(STORAGE_DIR, "users.json")
FILE_STORE_FILE = os.path.join(STORAGE_DIR, "files.json")
print(USER_STORE_FILE, FILE_STORE_FILE)

# ================= 服务器主密钥加载 =================
raw_key = os.getenv("ENCODE_KEY")
if raw_key is None:
    raise ValueError("未在环境变量中找到 ENCODE_KEY")

raw_key = raw_key.strip().strip('"').strip("'").replace(" ", "")
if raw_key.startswith("b64:"):
    SERVER_MASTER_KEY = base64.b64decode(raw_key[4:])
else:
    # 尝试 hex 解码，否则当作明文字符串 hash
    try:
        SERVER_MASTER_KEY = bytes.fromhex(raw_key)
    except ValueError:
        SERVER_MASTER_KEY = hashlib.sha256(raw_key.encode()).digest()

# 确保 32 字节
if len(SERVER_MASTER_KEY) != 32:
    SERVER_MASTER_KEY = hashlib.sha256(SERVER_MASTER_KEY).digest()

# ---------------- 内存缓存（同时也持久化到磁盘） ----------------
FILE_KEY_STORAGE: Dict[str, Dict[str, str]] = {}
USER_KEY_STORAGE: Dict[str, Dict[str, str]] = {}

# ---------------- 辅助：原子写文件 ----------------
def _atomic_write(path: str, data: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)

# ----------------- 持久化加载 / 保存 -----------------
def _load_json_safe(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # 如果文件损坏，返回空并备份旧文件
        try:
            os.rename(path, path + ".broken")
        except Exception:
            pass
        return {}

def load_stores():
    """从磁盘加载 USER_KEY_STORAGE 和 FILE_KEY_STORAGE"""
    global USER_KEY_STORAGE, FILE_KEY_STORAGE
    USER_KEY_STORAGE = _load_json_safe(USER_STORE_FILE)
    FILE_KEY_STORAGE = _load_json_safe(FILE_STORE_FILE)

def save_user_store():
    """保存 USER_KEY_STORAGE 到磁盘"""
    global USER_KEY_STORAGE
    _atomic_write(USER_STORE_FILE, json.dumps(USER_KEY_STORAGE, ensure_ascii=False, indent=2))

def save_file_store():
    """保存 FILE_KEY_STORAGE 到磁盘"""
    global FILE_KEY_STORAGE
    _atomic_write(FILE_STORE_FILE, json.dumps(FILE_KEY_STORAGE, ensure_ascii=False, indent=2))

# 初始加载（模块导入时加载一次）
load_stores()

# ================= 文件加密 =================
def node_crypto(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    服务器端加密流程（安全方案）：
    - 生成 file_key，用其加密数据
    - 用 SERVER_MASTER_KEY 加密 file_key 并保存到磁盘存储
    - 保存加密包到 MEDIA_ROOT/encrypted 并返回 URL，file_id

    现在会尝试从 state 中读取 "user_id" 和 "device_id" 并打印（如果有提供）
    """
    load_stores()  # 每次操作前 reload，保证进程之间能看到最新数据

    # 打印 user_id / device_id（兼容没有提供的情况）
    user_id = state.get("user_id") if isinstance(state, dict) else None
    device_id = state.get("device_id") if isinstance(state, dict) else None
    if user_id is None:
        user_id = "admin"
    if device_id is None:
        device_id = "admin"
    print(f"[node_crypto] user_id={user_id}, device_id={device_id}")

    data = state.get("data")
    if data is None:
        return {"error": "Missing 'data' field"}

    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")

    # 1. 生成 file_id 与 file_key
    file_id = uuid.uuid4().hex
    file_key = get_random_bytes(32)  # 随机文件密钥

    # 2. 用 file_key 加密数据
    nonce_data = get_random_bytes(12)
    cipher_data = AES.new(file_key, AES.MODE_GCM, nonce=nonce_data)
    ciphertext, tag_data = cipher_data.encrypt_and_digest(plaintext)

    # 3. 用 SERVER_MASTER_KEY 加密 file_key（用于服务器端保存）
    nonce_key = get_random_bytes(12)
    cipher_key = AES.new(SERVER_MASTER_KEY, AES.MODE_GCM, nonce=nonce_key)
    encrypted_file_key, tag_key = cipher_key.encrypt_and_digest(file_key)

    # 4. 保存到 FILE_KEY_STORAGE（持久化）
    FILE_KEY_STORAGE[file_id] = {
        "nonce": base64.b64encode(nonce_key).decode(),
        "tag": base64.b64encode(tag_key).decode(),
        "encrypted_key": base64.b64encode(encrypted_file_key).decode()
    }
    save_file_store()

    # 5. 打包加密文件（不包含 file_key）
    encrypted_package = {
        "version": "4.0",
        "file_id": file_id,
        "nonce": base64.b64encode(nonce_data).decode(),
        "tag": base64.b64encode(tag_data).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "notice": "此文件需要有效的许可证才能解密"
    }

    # 保存到磁盘
    filename = f"enc_{file_id[:8]}.json"
    file_path = os.path.join(MEDIA_ROOT, "encrypted", filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(encrypted_package, f, ensure_ascii=False, indent=2)

    download_url = f"{MEDIA_URL.rstrip('/')}/encrypted/{filename}"
    return {"url": download_url, "file_id": file_id, "message": "文件已加密，需要购买许可证才能解密"}







# 测试代码：
# ================= 用户密钥生成（PBKDF2） =================
def generate_user_key(user_id: str) -> str:
    """
    为用户生成唯一的用户密钥（base64 编码字符串）
    基于 SERVER_MASTER_KEY + user_id 派生，服务器端保存 user_key（base64）
    """
    salt = hashlib.sha256(f"user_{user_id}".encode()).digest()
    user_key = PBKDF2(SERVER_MASTER_KEY, salt, dkLen=32, count=100000)
    return base64.b64encode(user_key).decode()



# ================= 激活许可证 =================
def activate_license(user_id: str, device_id: str) -> Dict[str, str]:
    """
    用户购买许可证后，服务器生成 user_key 并保存（持久化）
    返回 user_key（base64）和 license_key
    """
    load_stores()  # reload storage
    license_id = uuid.uuid4().hex
    license_key = f"LIC-{license_id[:16].upper()}"
    user_key = generate_user_key(user_id)

    USER_KEY_STORAGE[user_id] = {"license_key": license_key, "user_key": user_key, "device_id": device_id}
    save_user_store()

    return {"license_key": license_key, "user_key": user_key, "message": "请将 user_key 保存到客户端"}

# ================= 获取文件解密密钥（在线验证） =================
def get_file_decrypt_key(user_id: str, file_id: str) -> Dict[str, Any]:
    """
    客户端请求解密密钥（在线验证）
    步骤：
      1. 验证用户是否存在且有许可证
      2. 验证 file_id 是否存在
      3. 用 SERVER_MASTER_KEY 解密存储的 encrypted_file_key，得到 file_key
      4. 用用户的 user_key（base64）重新加密 file_key，并返回给客户端
    """
    load_stores()  # reload to catch updates from other processes

    # 1. 验证用户
    if user_id not in USER_KEY_STORAGE:
        return {"error": "无效的用户ID或未购买许可证"}

    # 2. 验证文件
    if file_id not in FILE_KEY_STORAGE:
        return {"error": "文件不存在"}

    # 3. 用 SERVER_MASTER_KEY 解密文件密钥
    file_key_info = FILE_KEY_STORAGE[file_id]
    nonce_key = base64.b64decode(file_key_info["nonce"])
    tag_key = base64.b64decode(file_key_info["tag"])
    encrypted_file_key = base64.b64decode(file_key_info["encrypted_key"])

    cipher = AES.new(SERVER_MASTER_KEY, AES.MODE_GCM, nonce=nonce_key)
    file_key = cipher.decrypt_and_verify(encrypted_file_key, tag_key)

    # 4. 用 user_key 重新加密 file_key 返回
    user_info = USER_KEY_STORAGE[user_id]
    user_key = base64.b64decode(user_info["user_key"])
    nonce_user = get_random_bytes(12)
    cipher_user = AES.new(user_key, AES.MODE_GCM, nonce=nonce_user)
    encrypted_for_user, tag_user = cipher_user.encrypt_and_digest(file_key)

    return {
        "file_id": file_id,
        "nonce": base64.b64encode(nonce_user).decode(),
        "tag": base64.b64encode(tag_user).decode(),
        "encrypted_file_key": base64.b64encode(encrypted_for_user).decode(),
        "message": "文件解密密钥已准备好"
    }
# ---------------- 验证许可证 ----------------
def validate_license(user_id: str, license_key: str) -> Dict[str, Any]:
    """
    验证 user_id 与 license_key 是否存在且匹配。
    返回示例：
      {"valid": True, "user_id": user_id, "message": "..."}
      {"valid": False, "error": "..."}
    """
    load_stores()  # reload to get latest store
    if not user_id or not license_key:
        return {"valid": False, "error": "缺失 user_id 或 license_key"}

    # 如果用户存在并且 license_key 匹配
    info = USER_KEY_STORAGE.get(user_id)
    if info and info.get("license_key") == license_key:
        return {"valid": True, "user_id": user_id, "message": "许可证有效且已激活"}

    # 也支持通过 license_key 查找 user（如果需要）
    for uid, info in USER_KEY_STORAGE.items():
        if info.get("license_key") == license_key:
            # found license but user_id 不匹配
            return {"valid": False, "error": "license_key 属于其他用户", "owner_user_id": uid}

    return {"valid": False, "error": "无效的 user_id 或 license_key"}
