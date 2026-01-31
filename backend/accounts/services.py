import os
import base64
import hashlib
import logging
from typing import Dict, Tuple, Optional
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class CryptoService:
    """加密服务类（独立的加密逻辑）"""
    
    _SERVER_MASTER_KEY = None
    
    @classmethod
    def get_server_master_key(cls) -> bytes:
        """获取服务器主密钥（单例模式）- 强制从环境变量读取 Base64 编码的密钥"""
        if cls._SERVER_MASTER_KEY is not None:
            return cls._SERVER_MASTER_KEY
            
        raw_key = os.getenv("SERVER_MASTER_KEY")
        if not raw_key:
            raise ValueError("未在环境变量中找到 SERVER_MASTER_KEY")

        raw_key = raw_key.strip().strip('"').strip("'")
        
        # 强制要求 Base64 编码格式
        if not raw_key.startswith("b64:"):
            raise ValueError("SERVER_MASTER_KEY 必须以 'b64:' 开头的 Base64 格式")
        
        try:
            key = base64.b64decode(raw_key[4:])
        except Exception as e:
            raise ValueError(f"SERVER_MASTER_KEY Base64 解码失败: {e}")

        if len(key) != 32:
            raise ValueError(f"SERVER_MASTER_KEY 必须是 32 字节，当前为 {len(key)} 字节")
            
        cls._SERVER_MASTER_KEY = key
        logger.info("Server master key loaded successfully")
        return cls._SERVER_MASTER_KEY

    @classmethod
    def derive_user_key(cls, user_identifier: str) -> bytes:
        """
        基于服务器主密钥派生用户密钥
        
        Args:
            user_identifier: 用户唯一标识（通常是 user_id）
            
        Returns:
            bytes: 32字节的用户密钥
        """
        server_key = cls.get_server_master_key()
        salt = hashlib.sha256(f"user_{user_identifier}".encode()).digest()
        user_key = PBKDF2(server_key, salt, dkLen=32, count=100000)
        return user_key

    @classmethod
    def encrypt_file_key(cls, file_key: bytes) -> Dict[str, str]:
        """
        用服务器主密钥加密文件密钥
        
        Args:
            file_key: 原始文件密钥（32字节）
            
        Returns:
            Dict: 包含 nonce, tag, encrypted_key 的字典（base64编码）
        """
        server_key = cls.get_server_master_key()
        nonce = get_random_bytes(12)
        cipher = AES.new(server_key, AES.MODE_GCM, nonce=nonce)
        encrypted_key, tag = cipher.encrypt_and_digest(file_key)
        
        return {
            "nonce": base64.b64encode(nonce).decode(),
            "tag": base64.b64encode(tag).decode(),
            "encrypted_key": base64.b64encode(encrypted_key).decode()
        }

    @classmethod
    def decrypt_file_key(cls, encrypted_key_package: Dict[str, bytes]) -> bytes:
        """用服务器主密钥解密文件密钥"""
        master_key = cls.get_server_master_key()

        nonce = encrypted_key_package["nonce"]
        tag = encrypted_key_package["tag"]
        ciphertext = encrypted_key_package["encrypted_key"]

        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        decrypted_key = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted_key

    @classmethod
    def encrypt_for_user(cls, file_key: bytes, user_key_b64: str) -> Dict[str, str]:
        """
        用用户密钥加密文件密钥
        
        Args:
            file_key: 原始文件密钥
            user_key_b64: Base64编码的用户密钥
            
        Returns:
            Dict: 包含 nonce, tag, encrypted_key 的字典（base64编码）
        """
        user_key = base64.b64decode(user_key_b64)
        nonce = get_random_bytes(12)
        cipher = AES.new(user_key, AES.MODE_GCM, nonce=nonce)
        encrypted_key, tag = cipher.encrypt_and_digest(file_key)
        
        return {
            "nonce": base64.b64encode(nonce).decode(),
            "tag": base64.b64encode(tag).decode(),
            "encrypted_key": base64.b64encode(encrypted_key).decode()
        }

    @staticmethod
    def encrypt_content_with_key(plaintext_to_encrypt: bytes, key: bytes) -> Dict[str, str]:
        """用指定的密钥加密一段明文（通用函数）"""
        nonce = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext_to_encrypt)
        
        return {
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8'),
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
        }

    @classmethod
    def encrypt_file_content(cls, plaintext: bytes, file_key: bytes) -> Dict[str, str]:
        """
        用文件密钥加密文件内容
        
        Args:
            plaintext: 原始文件内容
            file_key: 文件密钥（32字节）
            
        Returns:
            Dict: 包含 nonce, tag, ciphertext 的字典（base64编码）
        """
        nonce = get_random_bytes(12)
        cipher = AES.new(file_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        
        return {
            "nonce": base64.b64encode(nonce).decode(),
            "tag": base64.b64encode(tag).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode()
        }

    @classmethod
    def decrypt_file_content(cls, nonce_b64: str, tag_b64: str, 
                            ciphertext_b64: str, file_key: bytes) -> bytes:
        """
        用文件密钥解密文件内容
        
        Args:
            nonce_b64: Base64编码的nonce
            tag_b64: Base64编码的tag
            ciphertext_b64: Base64编码的密文
            file_key: 文件密钥
            
        Returns:
            bytes: 解密后的原始内容
        """
        nonce = base64.b64decode(nonce_b64)
        tag = base64.b64decode(tag_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
        
        cipher = AES.new(file_key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext

    @classmethod
    def generate_file_key(cls) -> bytes:
        """生成随机文件密钥（32字节）"""
        return get_random_bytes(32)


# ==================== 便捷函数 ====================
def verify_license_validity(user) -> Tuple[bool, str]:
    """
    验证用户许可证有效性
    
    Args:
        user: User 对象
    
    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    if not hasattr(user, 'license_active'):
        return False, "用户模型缺少许可证字段"
    
    if not user.license_active:
        return False, "许可证未激活"
    
    if not user.license_key:
        return False, "许可证密钥不存在"
    
    if user.license_expires_at:
        from django.utils import timezone
        if timezone.now() > user.license_expires_at:
            return False, "许可证已过期"
    
    return True, "许可证有效"


def get_license_remaining_days(user) -> Optional[int]:
    """
    获取许可证剩余天数
    
    Args:
        user: User 对象
    
    Returns:
        int: 剩余天数（None 表示永久有效）
    """
    if not user.license_expires_at:
        return None
    
    from django.utils import timezone
    delta = user.license_expires_at - timezone.now()
    return max(0, delta.days)