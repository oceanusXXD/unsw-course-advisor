# decrypto_local.py (客户端, 放在 test/ 或其他运行位置)
import os
import json
import base64
import hashlib
from typing import Dict, Optional
from Crypto.Cipher import AES
from pathlib import Path
import sys

import requests

# ---------------- 配置 ----------------
# 指向你 Django API 的 base url
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
TEST_MODE = False  # False => 使用 HTTP API；True => 直接 import server module（本地测试）

# 将本地 license 存放到 项目 media/license_store/license.dat （你要求放在 media）
PROJECT_ROOT = Path(__file__).parent.parent.resolve()  # backend/
MEDIA_DIR = os.path.join(str(PROJECT_ROOT), "media")
LOCAL_LICENSE_FILE = os.path.join(MEDIA_DIR, "license_store", "client_license.dat")

# ---------------- 设备指纹 ----------------
def get_device_id() -> str:
    import uuid, platform
    features = [
        str(uuid.getnode()),
        platform.machine() or "",
        platform.processor() or "",
        platform.system() or ""
    ]
    combined = "|".join(features)
    return hashlib.sha256(combined.encode()).hexdigest()

# ---------------- 许可证管理 ----------------
class LicenseManager:
    def __init__(self):
        self.device_id = get_device_id()
        self.user_key: Optional[str] = None  # base64 字符串
        self.license_key: Optional[str] = None
        self.user_id: Optional[str] = None
        self.load_license()

    def load_license(self):
        if os.path.exists(LOCAL_LICENSE_FILE):
            try:
                with open(LOCAL_LICENSE_FILE, "rb") as f:
                    data = f.read()
                data = self._xor_obfuscate(data, self.device_id)
                info = json.loads(data.decode("utf-8"))
                self.license_key = info.get("license_key")
                self.user_key = info.get("user_key")
                self.user_id = info.get("user_id")
                print("✅ 已加载本地许可证")
            except Exception as e:
                print(f"⚠️ 加载许可证失败: {e}")

    def save_license(self, license_key: str, user_key: str, user_id: str):
        os.makedirs(os.path.dirname(LOCAL_LICENSE_FILE), exist_ok=True)
        info = {
            "license_key": license_key,
            "user_key": user_key,
            "user_id": user_id
        }
        data = json.dumps(info).encode("utf-8")
        enc = self._xor_obfuscate(data, self.device_id)
        with open(LOCAL_LICENSE_FILE, "wb") as f:
            f.write(enc)
        self.license_key = license_key
        self.user_key = user_key
        self.user_id = user_id
        print("✅ 许可证已保存到本地:", LOCAL_LICENSE_FILE)

    @staticmethod
    def _xor_obfuscate(data: bytes, key: str) -> bytes:
        k = key.encode()
        return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

    def is_activated(self) -> bool:
        return self.user_key is not None and self.user_id is not None

# ---------------- 客户端向服务器请求文件解密密钥 ----------------
def request_file_decrypt_key(user_id: str, file_id: str) -> Dict:
    """
    如果 TEST_MODE -> 直接调用本地模块（方便测试）
    否则通过 HTTP API 调用 /api/get_file_key/
    """
    if TEST_MODE:
        project_root = Path(__file__).parent.parent  # backend/
        sys.path.append(str(project_root))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
        import django
        django.setup()
        from chatbot.langgraph_agent.tools.crypto import get_file_decrypt_key
        return get_file_decrypt_key(user_id, file_id)

    url = f"{API_BASE_URL.rstrip('/')}/get_file_key/"
    resp = requests.post(url, json={"user_id": user_id, "file_id": file_id}, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ---------------- 解密逻辑（保留函数名 decrypt_file） ----------------
def decrypt_file(file_path: str, license_manager: LicenseManager) -> Dict:
    if not license_manager.is_activated():
        raise PermissionError("未激活许可证，请先激活")

    with open(file_path, "r", encoding="utf-8") as f:
        encrypted_package = json.load(f)

    version = encrypted_package.get("version", "4.0")
    if version != "4.0":
        raise ValueError(f"不支持的加密版本: {version}，需要 4.0")

    file_id = encrypted_package["file_id"]
    nonce = base64.b64decode(encrypted_package["nonce"])
    tag = base64.b64decode(encrypted_package["tag"])
    ciphertext = base64.b64decode(encrypted_package["ciphertext"])

    print(f"🔑 [Client] 请求文件密钥：file_id={file_id}")

    response = request_file_decrypt_key(license_manager.user_id, file_id)
    if "error" in response:
        raise PermissionError(response["error"])

    user_key_bytes = base64.b64decode(license_manager.user_key)
    key_nonce = base64.b64decode(response["nonce"])
    key_tag = base64.b64decode(response["tag"])
    encrypted_file_key = base64.b64decode(response["encrypted_file_key"])

    cipher_key = AES.new(user_key_bytes, AES.MODE_GCM, nonce=key_nonce)
    file_key = cipher_key.decrypt_and_verify(encrypted_file_key, key_tag)

    cipher_data = AES.new(file_key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher_data.decrypt_and_verify(ciphertext, tag)
    return json.loads(plaintext.decode("utf-8"))

def validate_license_via_api(user_id: str, license_key: str) -> Dict:
    """
    调用服务器 /api/validate_license/ 确认 license 是否有效。
    返回服务器 JSON（包含 valid 布尔字段或 error）。
    """
    if TEST_MODE:
        project_root = Path(__file__).parent.parent
        sys.path.append(str(project_root))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
        import django
        django.setup()
        from chatbot.langgraph_agent.tools.crypto import validate_license
        return validate_license(user_id, license_key)

    url = f"{API_BASE_URL.rstrip('/')}/validate_license/"
    resp = requests.post(url, json={"user_id": user_id, "license_key": license_key}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def activate_license_from_server_via_api(user_id: str, device_id: str):
    """
    通过 HTTP API 激活并把 license 保存到本地（MEDIA 下 license_store）
    - 先调用 activate_license API
    - 再调用 validate_license API 验证服务器返回的 license 是否真实有效
    - 验证通过则写本地
    """
    # 1) 请求服务器创建/返回 license
    if TEST_MODE:
        project_root = Path(__file__).parent.parent  # backend/
        sys.path.append(str(project_root))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
        import django
        django.setup()
        from chatbot.langgraph_agent.tools.crypto import activate_license
        act = activate_license(user_id, device_id)
    else:
        url = f"{API_BASE_URL.rstrip('/')}/activate_license/"
        resp = requests.post(url, json={"user_id": user_id, "device_id": device_id}, timeout=10)
        resp.raise_for_status()
        act = resp.json()

    # act 应包含 license_key 和 user_key
    license_key = act.get("license_key")
    user_key = act.get("user_key")
    if not license_key or not user_key:
        raise RuntimeError("服务器返回的激活信息不完整")

    # 2) 立即验证该 license 是否已激活（防止恶意/错误返回）
    print("🔎 正在验证服务器返回的 license 是否有效...")
    vres = validate_license_via_api(user_id, license_key)
    if not vres.get("valid"):
        # 若服务器端返回 error 说明未激活或不匹配
        err = vres.get("error", "未知错误，验证失败")
        raise RuntimeError(f"许可证验证失败: {err}")

    # 3) 验证通过，保存本地许可证
    lm = LicenseManager()
    lm.save_license(license_key, user_key, user_id)
    print("✅ 已将许可证写入本地（激活成功）")


# ---------------- test ----------------
def main():
    print("=" * 60)
    print("    🔓 MyPlugin - 客户端（HTTP 模式）")
    print("=" * 60)

    # 固定测试账号和设备
    test_user_id = "admin"
    test_device_id = "admin"

    lm = LicenseManager()
    if not lm.is_activated():
        print("⚠️ 当前未激活许可证，尝试通过 API 激活")
        try:
            activate_license_from_server_via_api(test_user_id, test_device_id)
            lm = LicenseManager()
        except Exception as e:
            print("激活失败:", e)
            return

    # 指定测试文件
    test_file_path = r"C:\Users\TAO\Desktop\chatbot\unsw-course-advisor\backend\media\encrypted\enc_51ecb7f2.json"
    print(f"📂 尝试解密文件: {test_file_path}")

    try:
        result = decrypt_file(test_file_path, lm)
        print("\n✅ 解密成功，内容如下：\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except PermissionError as e:
        print(f"\n❌ 权限错误: {e}")
    except Exception as e:
        print(f"\n❌ 解密失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

