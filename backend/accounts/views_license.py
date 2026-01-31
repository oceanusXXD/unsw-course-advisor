# 文件路径: (你的 app)/views.py

import os
import json
import uuid
import base64
import logging
from datetime import timedelta

# --- Django & DRF 核心模块 ---
from django.utils import timezone
from django.db import transaction
from django.contrib.staticfiles import finders # 关键导入，用于查找静态文件
from django.db import IntegrityError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

# --- 本地应用模块 ---
from .models import User, FileKey
from .serializers import LicenseActivateSerializer
from .services import CryptoService

logger = logging.getLogger(__name__)

# ================================================================
#                       许可证相关视图
# ================================================================

class ActivateLicenseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LicenseActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device_id = serializer.validated_data["device_id"]
        expires_in_days = serializer.validated_data.get("expires_in_days", 31)

        try:
            user_key_bytes = CryptoService.derive_user_key(str(request.user.id))
            user_key_b64 = base64.b64encode(user_key_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"为用户 {request.user.id} 派生 user_key 失败: {e}", exc_info=True)
            return Response({"error": "生成用户密钥失败"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        expires_at = timezone.now() + timedelta(days=expires_in_days)

        # 并发保护：行级锁 + 唯一键重试
        for _ in range(3):
            try:
                with transaction.atomic():
                    user = User.objects.select_for_update().get(pk=request.user.pk)
                    if user.license_active and user.license_key:
                        return Response({"error": "许可证已经激活"}, status=status.HTTP_409_CONFLICT)

                    license_key = f"LIC-{uuid.uuid4().hex[:16].upper()}"
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
                break
            except IntegrityError:
                # 罕见的 license_key 唯一冲突，重试生成
                continue
            except Exception as e:
                logger.error(f"保存许可证失败: {e}", exc_info=True)
                return Response({"error": "保存许可证失败"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({"error": "生成许可证失败，请重试"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": "许可证已成功激活（请妥善保存 user_key）",
            "license_key": user.license_key,
            "user_key": user.user_key,
            "device_id": user.device_id,
            "license_active": True,
            "license_expires_at": expires_at,
        }, status=status.HTTP_201_CREATED)

class ValidateLicenseView(APIView):
    """
    验证一个许可证密钥的有效性。
    这是一个公开接口。
    """
    permission_classes = [AllowAny]

    def post(self, request):
        license_key = request.data.get("license_key")
        if not license_key:
            return Response({"error": "请求中缺少 'license_key'"}, status=status.HTTP_400_BAD_REQUEST)

        # 使用 .select_related('user') 可能在未来有性能优势，如果需要访问更多用户信息
        user = User.objects.filter(license_key=license_key).first()

        if not user:
            return Response({"valid": False, "error": "许可证不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 复用 User 模型中定义的验证逻辑
        is_valid, reason = user.verify_license_validity()
        
        response_data = {
            "valid": is_valid,
            "reason": reason,
            "owner_user_id": user.id,
            "owner_email": user.email,
            "license_activated_at": user.license_activated_at,
            "license_expires_at": user.license_expires_at,
            "days_until_expiry": user.get_license_remaining_days()
        }
        
        if not is_valid:
            # 根据失败原因返回不同的状态码，便于客户端处理
            status_code = status.HTTP_402_PAYMENT_REQUIRED if "过期" in reason else status.HTTP_403_FORBIDDEN
            return Response(response_data, status=status_code)
            
        return Response(response_data, status=status.HTTP_200_OK)


class GetFileDecryptKeyView(APIView):
    """
    为持有有效许可证的用户提供经其 user_key 加密的文件密钥。
    这是一个公开接口，但需要有效的 license_key。
    """
    permission_classes = [AllowAny]

    def post(self, request):
        license_key = request.data.get("license_key")
        file_id = request.data.get("file_id")

        if not license_key or not file_id:
            return Response({"error": "请求中必须包含 'license_key' 和 'file_id'"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(license_key=license_key)
        except User.DoesNotExist:
            return Response({"error": "许可证无效或不存在"}, status=status.HTTP_403_FORBIDDEN)

        # 复用 User 模型中的验证逻辑
        is_valid, reason = user.verify_license_validity()
        if not is_valid:
            return Response({"error": f"许可证无效: {reason}"}, status=status.HTTP_403_FORBIDDEN)
        
        if not user.user_key:
            logger.error(f"用户 {user.id} 许可证有效但缺少 user_key")
            return Response({"error": "内部错误：用户密钥未设置"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            file_key_obj = FileKey.objects.get(file_id=file_id)
        except FileKey.DoesNotExist:
            return Response({"error": "文件ID无效或未找到对应密钥"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # 1. 用服务器主密钥解密存储在数据库中的文件密钥
            encrypted_key_package_bytes = {
                "nonce": base64.b64decode(file_key_obj.nonce),
                "tag": base64.b64decode(file_key_obj.tag),
                "encrypted_key": base64.b64decode(file_key_obj.encrypted_key)
            }
            plaintext_file_key = CryptoService.decrypt_file_key(encrypted_key_package_bytes)
            
            # 2. 用该用户的专属 user_key 重新加密文件密钥
            user_key_bytes = base64.b64decode(user.user_key)
            wrapped_file_key_for_user = CryptoService.encrypt_content_with_key(
                plaintext_to_encrypt=plaintext_file_key,
                key=user_key_bytes
            )
        except Exception as e:
            logger.error(f"为用户 {user.id} 处理文件密钥 {file_id} 时发生加密/解密错误: {e}", exc_info=True)
            return Response({"error": "处理密钥时发生内部错误"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": "文件解密密钥已成功封装",
            "wrapped_file_key": wrapped_file_key_for_user
        }, status=status.HTTP_200_OK)


class GetMyLicenseView(APIView):
    """
    返回当前已认证用户的许可证详细信息。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "license_key": user.license_key,
            "device_id": user.device_id,
            "license_active": user.license_active,
            "license_activated_at": user.license_activated_at,
            "license_expires_at": user.license_expires_at,
            "is_valid": user.is_license_valid,
            "days_until_expiry": user.get_license_remaining_days(),
        }, status=status.HTTP_200_OK)


# ================================================================
#                       静态内容视图
# ================================================================

class GetCourseMapView(APIView):
    """
    返回课程映射表。
    已优化为使用 Django 的静态文件查找器，与部署环境解耦。
    """
    permission_classes = [AllowAny]

    def get(self, request):
        # 使用 Django 的 finders 来查找静态文件，这会自动搜索所有已配置的静态文件目录
        relative_path = 'course_map.json'
        absolute_path = finders.find(relative_path) 

        if not absolute_path:
            logger.error(f"通过 Django finders 未能找到 '{relative_path}' 文件。请检查文件是否存在于某个 app 的 static/ 目录，或者 STATICFILES_DIRS 中。")
            return Response({"error": f"服务器内部错误：无法定位资源文件 '{relative_path}'"}, status=status.HTTP_404_NOT_FOUND)

        try:
            with open(absolute_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
             # 这是一个额外的保险，理论上 finders.find() 已经处理了
            logger.error(f"文件 '{absolute_path}' 物理上不存在，即使 finders 找到了它。")
            return Response({"error": "资源文件不存在"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"读取或解析课程映射文件 '{absolute_path}' 失败: {e}", exc_info=True)
            return Response({"error": "读取资源文件时发生错误", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(data, status=status.HTTP_200_OK)