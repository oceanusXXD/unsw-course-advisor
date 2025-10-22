# views.py — 完整文件（基于你给的版本，GetFileDecryptKeyView 已修改以优先使用 DB）
import json
import logging
import base64
import uuid
from typing import Any, Dict
from datetime import timedelta
import os
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .email_utils import send_license_email
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
            # 直接调用 CryptoService 中统一的、健壮的方法
            user_key_bytes = CryptoService.derive_user_key(str(user.id))
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
    """验证许可证有效性 - 无需认证"""
    permission_classes = [AllowAny]

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

        return self._build_response(user_with_license, is_expired)

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

    def _build_response(self, license_user, is_expired):
        """构建标准化响应"""
        response_data = {
            "valid": not is_expired,
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
    通过 license_key 识别用户，无需预先认证
    """
    permission_classes = [AllowAny]  # 改为允许匿名访问

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

        # 2. 通过 license_key 查找用户（替代 request.user）
        try:
            user = User.objects.get(license_key=license_key)
        except User.DoesNotExist:
            return Response({"error": "许可证无效或不存在"}, status=403)

        # 3. 验证许可证状态
        if not user.license_active:
            return Response({"error": "许可证未激活"}, status=403)
        if user.license_expires_at and timezone.now() > user.license_expires_at:
            return Response({"error": "许可证已过期"}, status=403)
        if not user.user_key:
            return Response({"error": "用户密钥(user_key)未设置，无法提供解密服务"}, status=403)

        try:
            # 4. 从数据库查找文件密钥记录
            try:
                file_key_obj = FileKey.objects.get(file_id=file_id)
            except FileKey.DoesNotExist:
                return Response({"error": "文件ID无效或未找到对应的密钥"}, status=404)
            
            master_key_b64 = os.getenv("SERVER_MASTER_KEY")
            logger.info(f"[解密端] 正在为 file_id '{file_id}' 解密密钥")
            
            # 5. 用服务器主密钥解密，得到明文 file_key
            encrypted_key_from_db = {
                "nonce": file_key_obj.nonce,
                "tag": file_key_obj.tag,
                "encrypted_key": file_key_obj.encrypted_key,
            }
            
            # 将 base64 字符串转换为 bytes
            encrypted_key_package_bytes = {
                "nonce": base64.b64decode(encrypted_key_from_db["nonce"]),
                "tag": base64.b64decode(encrypted_key_from_db["tag"]),
                "encrypted_key": base64.b64decode(encrypted_key_from_db["encrypted_key"])
            }

            # 解密得到明文 file_key
            plaintext_file_key = CryptoService.decrypt_file_key(encrypted_key_package_bytes)

            # 6. 用 user_key 重新加密 file_key
            user_key_bytes = base64.b64decode(user.user_key)
            
            encrypted_fk_for_user = CryptoService.encrypt_content_with_key(
                plaintext_to_encrypt=plaintext_file_key,
                key=user_key_bytes
            )

            # 7. 返回给前端
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
    """返回当前用户的许可证信息（需要认证）"""
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

def resolve_course_map_path(env_path):
    """
    将环境变量路径解析为绝对路径，支持相对路径（相对于 manage.py 的启动工作目录）
    """
    if not env_path:
        return None
    # 展开 ~ 并转为绝对路径
    env_path = os.path.expanduser(env_path)
    return os.path.abspath(env_path)

class GetCourseMapView(APIView):
    """
    GET /accounts/get_course/?keys=GSOE9011,COMP9101[&term=T2]
    返回:
    {
      "success": true,
      "data": {
         "COMP9101": [
            { "course_id": "...", "term_code": "5266", "term": "T2", "section":"1", "prefix":"0058351" },
            ...
         ],
         ...
      }
    }
    需要认证 (IsAuthenticated)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        keys_param = request.GET.get("keys", "")
        term_filter = request.GET.get("term", "").strip()  # 可传 "T1"/"T2"/"T3" 或 "t1"
        if not keys_param:
            return Response({"success": False, "error": "缺少 keys 参数"}, status=400)

        requested_keys = [k.strip() for k in keys_param.split(",") if k.strip()]
        if not requested_keys:
            return Response({"success": False, "error": "keys 参数为空"}, status=400)

        # 从环境变量读取路径并解析为绝对路径
        env_path = os.getenv("COURSE_MAP_PATH")
        json_path = resolve_course_map_path(env_path)
        if not json_path or not os.path.exists(json_path):
            return Response({"success": False, "error": "course_map.json 路径无效或不存在", "path": json_path}, status=500)

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                course_map = json.load(f)
        except Exception as e:
            return Response({"success": False, "error": f"读取 course_map.json 失败: {str(e)}"}, status=500)

        # 结果组织：对于每个请求的 key 返回 list（可能为空）
        result = {}
        term_filter_norm = term_filter.upper() if term_filter else None

        for k in requested_keys:
            entries = course_map.get(k, [])
            if not isinstance(entries, list):
                # 兼容旧单值格式：如果 value 是字符串，则转成 list
                if isinstance(entries, str) and entries:
                    entries = [{"course_id": entries}]
                else:
                    entries = []

            # 如果有 term_filter，则用 entry["term"] 进行过滤（例如 "T2"）
            if term_filter_norm:
                filtered = [e for e in entries if (e.get("term") and e.get("term").upper() == term_filter_norm)]
            else:
                filtered = entries

            result[k] = filtered

        return Response({"success": True, "data": result})

#class StripeWebhookView(APIView):
#    permission_classes = [AllowAny] # Webhook 不需要用户登录
#
#    def post(self, request):
#        payload = request.body
#        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
#        # 假设你在 settings.py 中有 STRIPE_WEBHOOK_SECRET
#        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
#
#        if not webhook_secret:
#            logger.error("Stripe webhook secret 未配置！")
#            return Response(status=500)
#
#        try:
#            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
#        except (ValueError, stripe.error.SignatureVerificationError) as e:
#            return Response(status=400)
#
#        if event['type'] == 'checkout.session.completed':
#            session = event['data']['object']
#            email = session.get('customer_email')
#            duration_days = int(session.get('metadata', {}).get('duration_days', 365))
#
#            if not email:
#                return Response(status=400)
#
#            # 找到用户或创建新用户
#            user, created = User.objects.get_or_create(email=email)
#            if created:
#                user.set_unusable_password() # 如果是新用户，先设置一个不可用密码
#                user.save()
#
#            # 为用户生成许可证信息
#            user.license_key = f"LIC-{uuid.uuid4().hex[:16].upper()}"
#            user.license_expires_at = timezone.now() + timedelta(days=duration_days)
#            user.license_active = False # 重要：只发放，不激活
#            user.save()
#
#            # 发送邮件
#            try:
#                send_license_email(user.email, user.license_key)
#            except Exception as e:
#                logger.error(f"发送许可证邮件失败: {e}")
#
#        return Response(status=200)