# 文件路径: unsw-course-advisor\backend\accounts\views_login.py

# ======================== 依赖导入 ========================
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError
import logging

from .models import User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    UserDetailSerializer
)

logger = logging.getLogger(__name__)


# ======================== 辅助函数 ========================
def get_tokens_for_user(user):
    """为用户生成 JWT tokens"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def extract_validation_message(detail):
    """
    从 ValidationError.detail 提取首条可读消息（返回字符串）
    支持 dict/list/其他结构。
    """
    try:
        if isinstance(detail, dict):
            first_key = next(iter(detail))
            val = detail[first_key]
            if isinstance(val, (list, tuple)) and val:
                return str(val[0])
            return str(val)
        if isinstance(detail, (list, tuple)) and detail:
            return str(detail[0])
        return str(detail)
    except Exception:
        return str(detail)


# ======================== 用户注册 ========================
class RegisterView(generics.CreateAPIView):
    """用户注册"""
    permission_classes = [AllowAny]
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"Registration attempt with data: {request.data}")
        # 使用 copy 以避免不可变 QueryDict 问题
        data = request.data.copy()
        # 兼容：若前端未传 password2，则用 password 填充（兜底）
        if 'password2' not in data and 'password' in data:
            data['password2'] = data['password']

        try:
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            tokens = get_tokens_for_user(user)

            logger.info(f"User registered: {user.email}")

            # 统一成功返回结构：顶层 access/refresh，同时保留 tokens 对象
            return Response({
                "message": "注册成功",
                "user": {"id": user.id, "email": user.email, "username": user.username},
                "tokens": tokens,
                "access": tokens['access'],
                "refresh": tokens['refresh']
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            # 提取首条错误信息并以统一结构返回
            message = extract_validation_message(e.detail)
            logger.warning(f"Registration validation failed: {message}")
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(f"Registration failed: {e}")
            # 返回简洁错误信息（避免把复杂的 exception detail 泄露给客户端）
            return Response({"error": "注册过程中发生错误"}, status=status.HTTP_400_BAD_REQUEST)


# ======================== 登录 ========================
class LoginView(APIView):
    """用户登录"""
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        logger.info(f"Login attempt with data: {request.data}")

        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)

            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)

            logger.info(f"User logged in: {user.email}")

            # 统一成功返回结构：顶层 access/refresh，同时保留 tokens 对象
            return Response({
                "access": tokens['access'],
                "refresh": tokens['refresh'],
                "user": {"id": user.id, "email": user.email, "username": user.username},
                "tokens": tokens
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            message = extract_validation_message(e.detail)
            logger.warning(f"Login validation failed: {message}")
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(f"Login error: {e}")
            return Response({"error": "登录失败"}, status=status.HTTP_401_UNAUTHORIZED)


# ======================== 当前用户 ========================
class CurrentUserView(APIView):
    """获取当前用户信息"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserDetailSerializer

    def get(self, request):
        user = request.user
        serializer = self.serializer_class(user)
        data = serializer.data

        logger.info(f"Current user info requested: {user.email}")
        return Response({"user": data}, status=status.HTTP_200_OK)


# ======================== 注销 ========================
class LogoutView(APIView):
    """用户登出"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        logger.info(f"Logout attempt for user: {request.user.email}")

        if not refresh_token:
            logger.warning("Logout failed: no refresh token provided")
            return Response({"error": "需要提供 refresh token"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"User {request.user.email} logged out")
            return Response({"detail": "登出成功，token 已失效"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Logout error: {e}")
            return Response({"error": "登出失败"}, status=status.HTTP_400_BAD_REQUEST)


# ======================== 修改密码 ========================
class ChangePasswordView(APIView):
    """修改密码"""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"User {request.user.email} changed password successfully")
            return Response({"detail": "密码修改成功"}, status=status.HTTP_200_OK)
        except ValidationError as e:
            message = extract_validation_message(e.detail)
            logger.warning(f"Change password validation failed: {message}")
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Change password error: {e}")
            return Response({"error": "密码修改失败"}, status=status.HTTP_400_BAD_REQUEST)


# ======================== 删除用户 ========================
class DeleteUserView(generics.DestroyAPIView):
    """删除用户"""
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        logger.info(f"User {user.email} is deleting account...")
        self.perform_destroy(user)
        logger.info(f"User {user.email} deleted account")
        return Response({"message": "账号已成功删除"}, status=status.HTTP_200_OK)