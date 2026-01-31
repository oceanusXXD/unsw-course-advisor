import os
import json
import uuid
import logging
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# 媒体文件配置
MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(os.getcwd(), "media"))
MEDIA_URL = os.getenv("MEDIA_URL", "http://localhost/media/")
os.makedirs(os.path.join(MEDIA_ROOT, "encrypted"), exist_ok=True)


def node_crypto(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph 加密节点：生成加密文件并保存文件密钥到数据库
    
    Args:
        state: 包含以下字段的字典
            - data: 要加密的数据（dict/list）
            - user_id: 用户ID（可选）
            - device_id: 设备ID（可选）
            
    Returns:
        Dict: 包含加密文件的下载URL和file_id
    """
    # 导入 Django 相关模块（延迟导入，避免循环依赖）
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
        if not django.apps.apps.ready:
            django.setup()
    except Exception as e:
        logger.warning(f"Django setup warning: {e}")

    from accounts.models import FileKey, User
    from accounts.services import CryptoService

    # 获取参数
    user_id = state.get("user_id", "admin")
    device_id = state.get("device_id", "admin")
    data = state.get("data")

    if data is None:
        return {"error": "Missing 'data' field"}

    logger.debug(f"[node_crypto] user_id={user_id}, device_id={device_id}")

    try:
        # 1. 准备明文数据
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        print(f"--- [加密端] 加载的主密钥是: {os.getenv('SERVER_MASTER_KEY')} ---")
        # 2. 生成文件ID和文件密钥
        file_id = uuid.uuid4().hex
        file_key = CryptoService.generate_file_key()

        # 3. 用文件密钥加密内容
        encrypted_content = CryptoService.encrypt_file_content(plaintext, file_key)

        # 4. 用服务器主密钥加密文件密钥
        encrypted_file_key = CryptoService.encrypt_file_key(file_key)

        # 5. 保存到数据库
        try:
            # 尝试获取用户对象
            user_obj = None
            if user_id and user_id != "admin":
                try:
                    user_obj = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    logger.warning(f"User {user_id} not found, creating FileKey without user")

            FileKey.objects.update_or_create(
                file_id=file_id,
                defaults={
                    "nonce": encrypted_file_key["nonce"],
                    "tag": encrypted_file_key["tag"],
                    "encrypted_key": encrypted_file_key["encrypted_key"],
                    "creator_user": user_obj,
                    "creator_device_id": device_id
                }
            )
            logger.info(f"FileKey saved to database: {file_id}")
        except Exception as e:
            logger.error(f"Failed to save FileKey to database: {e}", exc_info=True)
            return {"error": f"Failed to save file key: {str(e)}"}

        # 6. 生成加密文件包
        # 注意：如果你需要前端直接用 user_key 解这个包，请把内容用 user_key 加密，
        # 或者在包里包含一个用 user_key 包裹的 file_key。这里先保持原样（用 file_key 加密内容）。
        encrypted_package = {
            "version": "5.0",
            "file_id": file_id,
            "nonce": encrypted_content["nonce"],
            "tag": encrypted_content["tag"],
            "ciphertext": encrypted_content["ciphertext"],
            "notice": "此文件需要有效的许可证才能解密"
        }

        # 7. 保存到文件系统
        filename = f"enc_{file_id[:8]}.json"
        file_path = os.path.join(MEDIA_ROOT, "encrypted", filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(encrypted_package, f, ensure_ascii=False, indent=2)

        # 8. 返回下载URL
        download_url = f"{MEDIA_URL.rstrip('/')}/encrypted/{filename}"
        
        return {
            "url": download_url,
            "file_id": file_id,
            "message": "文件已加密，需要有效许可证才能解密"
        }

    except Exception as e:
        logger.error(f"Encryption failed: {str(e)}", exc_info=True)
        return {"error": f"Encryption failed: {str(e)}"}


def decrypt_file(encrypted_package: Dict[str, Any], file_key: bytes) -> Any:
    """
    解密文件内容
    
    Args:
        encrypted_package: 加密文件包（包含 nonce, tag, ciphertext）
        file_key: 文件密钥
        
    Returns:
        解密后的数据（原始 dict/list）
    """
    from accounts.services import CryptoService
    
    try:
        plaintext = CryptoService.decrypt_file_content(
            nonce_b64=encrypted_package["nonce"],
            tag_b64=encrypted_package["tag"],
            ciphertext_b64=encrypted_package["ciphertext"],
            file_key=file_key
        )
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to decrypt file: {str(e)}")