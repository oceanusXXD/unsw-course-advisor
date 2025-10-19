# views.py — 完整文件（基于你给的版本，GetFileDecryptKeyView 已修改以优先使用 DB）
import logging
import base64
import uuid
from typing import Any, Dict
from datetime import timedelta
import os
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from accounts.models import FileKey
from accounts.services import CryptoService
from .models import User
from .serializers import RegisterSerializer, LoginSerializer, LicenseActivateSerializer
from chatbot.langgraph_agent.tools import crypto
from dotenv import load_dotenv
# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 从环境变量获取配置
class EnvConfig:
    @staticmethod
    def get_required(key: str) -> str:
        value = os.getenv(key)
        if value is None:
            raise EnvironmentError(f"必需的环境变量 {key} 未设置")
        return value

    @staticmethod
    def get_required_bytes(key: str, encoding: str = 'utf-8') -> bytes:
        return EnvConfig.get_required(key).encode(encoding)

    @staticmethod
    def get_required_base64(key: str) -> bytes:
        return base64.b64decode(EnvConfig.get_required(key))

# 使用方式
SERVER_MASTER_KEY = EnvConfig.get_required_bytes('SERVER_MASTER_KEY')
# ======================== 辅助函数 ========================
def get_tokens_for_user(user):
    """生成JWT令牌"""
    try:
        logger.debug(f"Attempting to generate tokens for user: {user.email}")
        refresh = RefreshToken.for_user(user)
        logger.debug(f"Refresh token generated: {str(refresh)}")
        access_token = str(refresh.access_token)
        logger.debug(f"Access token generated: {access_token}")
        
        return {
            'refresh_token': str(refresh),
            'access_token': access_token,
        }
    except Exception as e:
        logger.error(f"Token generation failed for user {getattr(user, 'email', user)}: {str(e)}", exc_info=True)
        raise

def _derive_user_key(server_master_key: bytes, user_identifier: str) -> bytes:
    """
    基于服务器主密钥与user_identifier派生user_key
    PBKDF2(server_master_key, salt=user_userid_sha256, dkLen=32, count=100000)
    返回 raw bytes
    """
    salt = __import__("hashlib").sha256(f"user_{user_identifier}".encode()).digest()
    user_key = PBKDF2(server_master_key, salt, dkLen=32, count=100000)
    return user_key

# ======================== 用户认证视图 ========================
class RegisterView(generics.CreateAPIView):
    """用户注册"""
    permission_classes = [AllowAny]
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"Registration attempt with data: {request.data}")
        
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            logger.debug("Serializer validation passed")
            
            user = serializer.save()
            logger.info(f"User created: {user.email}")
            
            tokens = get_tokens_for_user(user)
            logger.debug("Tokens generated successfully")
            
            return Response({
                "message": "注册成功",
                "user": {
                    "email": user.email,
                    "username": user.username
                },
                "tokens": tokens
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Registration failed: {str(e)}", exc_info=True)
            return Response({
                "error": str(e),
                "details": "注册过程中发生错误"
            }, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    """用户登录"""
    permission_classes = [AllowAny]
    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({
                "error": "Authentication failed",
                "details": str(e)
            }, status=status.HTTP_401_UNAUTHORIZED)

class CurrentUserView(APIView):
    """获取当前用户信息"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            logger.debug(f"CurrentUser requested by: {user.email if hasattr(user, 'email') else user}")
            data = {
                "id": user.id,
                "email": getattr(user, "email", None),
                "username": getattr(user, "username", None),
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "date_joined": user.date_joined,
                "last_login": user.last_login,
                # 把许可相关非敏感字段返回给前端
                "license": {
                    "license_key": getattr(user, "license_key", None),
                    "device_id": getattr(user, "device_id", None),
                    "license_active": getattr(user, "license_active", False),
                    "license_activated_at": getattr(user, "license_activated_at", None),
                    "license_expires_at": getattr(user, "license_expires_at", None),
                }
            }
            return Response({"user": data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error getting current user: {str(e)}", exc_info=True)
            return Response({"error": "无法获取当前用户信息", "details": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LogoutView(APIView):
    """用户注销"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "需要提供 refresh token"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"Refresh token blacklisted for user {request.user.email}")
            return Response({"detail": "已登出（refresh token 已被拉黑）"}, status=status.HTTP_200_OK)
        except AttributeError:
            logger.warning("Token blacklist not enabled or not available.")
            return Response({"detail": "已登出，但服务器未启用 token blacklist（请在 settings 中启用）"},
                            status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Logout error: {str(e)}", exc_info=True)
            return Response({"error": "登出失败", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    """修改密码"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response({"error": "需要 old_password 和 new_password"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if not user.check_password(old_password):
                return Response({"error": "原密码不正确"}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.save()
            logger.info(f"Password changed for user {user.email}")
            return Response({"detail": "密码修改成功"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Change password failed for user {user.email}: {str(e)}", exc_info=True)
            return Response({"error": "修改密码失败", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ======================== 许可证管理视图（单表：User 包含许可证） ========================
class ActivateLicenseView(APIView):
    """激活许可证（把许可证写入 User 表）"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LicenseActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = serializer.validated_data["device_id"]

        user = request.user
        license_key = f"LIC-{uuid.uuid4().hex[:16].upper()}"
        
        try:
            user_key_bytes = _derive_user_key(SERVER_MASTER_KEY, str(user.id))
            user_key_b64 = base64.b64encode(user_key_bytes).decode()
        except Exception as e:
            logger.error("派生 user_key 失败: %s", e, exc_info=True)
            return Response({"error": "生成 user_key 失败", "details": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 默认有效期（可修改）：365 天
        expires_at = timezone.now() + timedelta(days=365)

        try:
            # 将许可证信息写入 User 表（单表方案）
            user.license_key = license_key
            user.user_key = user_key_b64
            user.device_id = device_id
            user.license_activated_at = timezone.now()
            user.license_expires_at = expires_at
            user.license_active = True
            user.save(update_fields=[
                "license_key", "user_key", "device_id",
                "license_activated_at", "license_expires_at", "license_active"
            ])
        except Exception as e:
            logger.error("保存许可证到用户表失败: %s", e, exc_info=True)
            return Response({"error": "保存许可证失败", "details": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "license_key": license_key,
            "user_key": user_key_b64,
            "device_id": device_id,
            "license_active": True,
            "license_expires_at": expires_at,
            "message": "许可证已激活（请妥善保存 user_key）"
        }, status=status.HTTP_201_CREATED)

class ValidateLicenseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        验证许可证有效性
        请求参数:
        {
            "license_key": "许可证密钥字符串"
        }
        返回:
        - 有效且未过期: HTTP 200
        - 无效或过期: HTTP 400
        """
        # 统一处理请求数据
        try:
            data = self._parse_request_data(request)
            license_key = self._validate_license_key(data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 查询许可证信息
        user_with_license = User.objects.filter(license_key=license_key).first()
        if not user_with_license:
            return Response(
                {"valid": False, "error": "许可证不存在"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查过期状态
        is_expired = self._check_license_expiry(user_with_license)

        return self._build_response(user_with_license, request.user, is_expired)

    def _parse_request_data(self, request):
        """解析请求数据，支持JSON字符串和字典格式"""
        data = request.data
        if isinstance(data, str):
            try:
                import json
                return json.loads(data)
            except json.JSONDecodeError:
                raise ValueError("请求体不是有效JSON")
        return data

    def _validate_license_key(self, data):
        """验证并提取license_key"""
        license_key = data.get("license_key")
        if not license_key:
            raise ValueError("缺失 license_key")
        return license_key

    def _check_license_expiry(self, user):
        """检查许可证是否过期"""
        return (
            user.license_expires_at and 
            timezone.now() > user.license_expires_at
        )

    def _build_response(self, license_user, requesting_user, is_expired):
        """构建标准化响应"""
        response_data = {
            "valid": not is_expired,
            "is_owner": license_user.id == requesting_user.id,
            "owner_user_id": license_user.id,
            "owner_email": license_user.email,
            "expired": is_expired,
            "license_active": license_user.license_active,
            "license_activated_at": license_user.license_activated_at,
            "license_expires_at": license_user.license_expires_at
        }
        return Response(
            response_data,
            status=status.HTTP_200_OK if not is_expired else status.HTTP_400_BAD_REQUEST
        )

class GetFileDecryptKeyView(APIView):
    """
    获取经用户 user_key 加密的文件密钥 (file_key)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. 获取前端传入的参数
        encrypted_file = request.data.get("encrypted_file")
        license_key = request.data.get("license_key")

        if not encrypted_file or not isinstance(encrypted_file, dict):
            return Response({"error": "缺失或无效的 'encrypted_file'"}, status=400)
        if not license_key:
            return Response({"error": "缺失 'license_key'"}, status=400)
        
        file_id = encrypted_file.get("file_id")
        if not file_id:
            return Response({"error": "加密文件中缺少 'file_id'"}, status=400)

        # 2. 验证用户和许可证
        user = request.user
        if user.license_key != license_key:
            return Response({"error": "许可证无效或不属于当前用户"}, status=403)
        if not user.license_active:
            return Response({"error": "许可证未激活"}, status=403)
        if user.license_expires_at and timezone.now() > user.license_expires_at:
            return Response({"error": "许可证已过期"}, status=403)
        if not user.user_key:
            return Response({"error": "用户密钥(user_key)未设置，无法提供解密服务"}, status=403)

        try:
            # 3. 从数据库查找文件密钥记录
            try:
                file_key_obj = FileKey.objects.get(file_id=file_id)
            except FileKey.DoesNotExist:
                return Response({"error": "文件ID无效或未找到对应的密钥"}, status=404)
            master_key_b64 = os.getenv("SERVER_MASTER_KEY")
            print(f"--- [解密端] 加载的主密钥是: {master_key_b64} ---")
            # 4. 用服务器主密钥解密，得到明文 file_key
            #    注意: 这依赖于你的 CryptoService 中有 decrypt_file_key 方法
            encrypted_key_from_db = {
                "nonce": file_key_obj.nonce,
                "tag": file_key_obj.tag,
                "encrypted_key": file_key_obj.encrypted_key,
            }
            encrypted_key_package_bytes = {
                # 对每一个值都进行 base64 解码，从 str 转换为 bytes
                "nonce": base64.b64decode(encrypted_key_from_db["nonce"]),
                "tag": base64.b64decode(encrypted_key_from_db["tag"]),
                # 假设加密密钥的键名是 "encrypted_key"
                "encrypted_key": base64.b64decode(encrypted_key_from_db["encrypted_key"])
            }

            # 2. 将这个新创建的、类型正确的字典传递给函数
            plaintext_file_key = CryptoService.decrypt_file_key(encrypted_key_package_bytes)

            # 3. 接下来处理 user_key (这里也需要解码)
            #    user.user_key 从数据库读出来也是 str，需要解码成 bytes
            user_key_bytes = base64.b64decode(user.user_key)
            
            # 使用一个新的加密函数来包裹密钥，避免和加密文件内容混淆
            # 这本质上和 encrypt_file_content 逻辑一样，只是操作对象是 file_key
            encrypted_fk_for_user = CryptoService.encrypt_content_with_key(
                plaintext_to_encrypt=plaintext_file_key,
                key=user_key_bytes
            )

            # 6. 返回给前端
            return Response({
                "message": "文件解密密钥已成功生成，并由您的 user_key 加密。",
                "wrapped_file_key": {
                    "nonce": encrypted_fk_for_user["nonce"],
                    "tag": encrypted_fk_for_user["tag"],
                    "ciphertext": encrypted_fk_for_user["ciphertext"],
                }
            }, status=200)

        except Exception as e:
            logger.error(f"为 file_id '{file_id}' 生成解密密钥失败: {e}", exc_info=True)
            return Response({"error": "处理密钥时发生内部错误", "details": str(e)}, status=500)

class GetMyLicenseView(APIView):
    """返回当前用户的许可证信息（不包含敏感 user_key）"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            "license_key": u.license_key,
            "device_id": u.device_id,
            "license_active": u.license_active,
            "license_activated_at": u.license_activated_at,
            "license_expires_at": u.license_expires_at,
        }, status=status.HTTP_200_OK)
