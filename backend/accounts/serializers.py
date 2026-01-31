# 文件路径: unsw-course-advisor\backend\accounts\serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Feedback

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """用户注册序列化器"""
    password = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'},
        help_text="密码至少8位"
    )
    password2 = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'},
        help_text="确认密码"
    )
    email = serializers.EmailField(
        required=True,
        help_text="邮箱地址"
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password2')
        extra_kwargs = {
            'username': {'required': False},
        }

    def validate_email(self, value):
        """验证邮箱唯一性"""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("该邮箱已被注册")
        return value.lower()

    def validate_password(self, value):
        """验证密码强度"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        """验证两次密码是否一致"""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password2": "两次输入的密码不一致"
            })
        return attrs

    def create(self, validated_data):
        """创建用户"""
        # 移除 password2，不需要保存
        validated_data.pop('password2')
        
        # 如果没有提供 username，使用邮箱前缀
        if not validated_data.get('username'):
            email_prefix = validated_data['email'].split('@')[0]
            base_username = email_prefix
            username = base_username
            counter = 1
            
            # 确保 username 唯一
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            validated_data['username'] = username
        
        # 创建用户
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password']
        )
        
        return user


class LoginSerializer(serializers.Serializer):
    """用户登录序列化器"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, data):
        """验证登录信息"""
        email = data.get('email', '').lower()
        password = data.get('password')

        if not email or not password:
            raise serializers.ValidationError("邮箱和密码都是必填项")

        # 查找用户
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("邮箱或密码错误")

        # 验证密码
        if not user.check_password(password):
            raise serializers.ValidationError("邮箱或密码错误")

        # 检查用户是否激活
        if not user.is_active:
            raise serializers.ValidationError("该账号已被禁用，请联系管理员")

        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    """用户信息序列化器"""
    
    class Meta:
        model = User
        fields = (
            'id', 
            'email', 
            'username', 
            'is_active', 
            'is_staff',
            'date_joined', 
            'last_login'
        )
        read_only_fields = fields


class UserDetailSerializer(serializers.ModelSerializer):
    """用户详细信息序列化器（包含许可证信息）"""
    license = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'is_active',
            'is_staff',
            'date_joined',
            'last_login',
            'license'
        )
        read_only_fields = fields

    def get_license(self, obj):
        """获取许可证信息"""
        return {
            "license_key": getattr(obj, "license_key", None),
            "device_id": getattr(obj, "device_id", None),
            "license_active": getattr(obj, "license_active", False),
            "license_activated_at": getattr(obj, "license_activated_at", None),
            "license_expires_at": getattr(obj, "license_expires_at", None),
        }


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码序列化器"""
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_old_password(self, value):
        """验证旧密码"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("原密码不正确")
        return value

    def validate_new_password(self, value):
        """验证新密码强度"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        """验证两次密码是否一致"""
        # 检查新密码是否与旧密码相同
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                "new_password": "新密码不能与旧密码相同"
            })
        
        return attrs

    def save(self, **kwargs):
        """保存新密码"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """密码重置请求序列化器（可选功能）"""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """验证邮箱是否存在"""
        try:
            User.objects.get(email=value.lower())
        except User.DoesNotExist:
            # 为了安全，不透露邮箱是否存在
            # 但在内部记录这个尝试
            pass
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """密码重置确认序列化器（可选功能）"""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password2 = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_new_password(self, value):
        """验证新密码强度"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        """验证两次密码是否一致"""
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password2": "两次输入的密码不一致"
            })
        return attrs


class SocialAuthSerializer(serializers.Serializer):
    """社交登录序列化器"""
    access_token = serializers.CharField(required=True)
    
    def validate_access_token(self, value):
        """验证 access token"""
        if not value:
            raise serializers.ValidationError("access_token 不能为空")
        return value


class LicenseActivateSerializer(serializers.Serializer):
    """许可证激活序列化器"""
    device_id = serializers.CharField(max_length=128, required=True)
    expires_in_days = serializers.IntegerField(
        required=False, default=365, min_value=1, max_value=3650
    )


class LicenseInfoSerializer(serializers.ModelSerializer):
    """许可证信息序列化器"""
    is_valid = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'license_key',
            'device_id',
            'license_active',
            'license_activated_at',
            'license_expires_at',
            'is_valid',
            'days_until_expiry'
        )

    def get_is_valid(self, obj):
        return obj.is_license_valid

    def get_days_until_expiry(self, obj):
        if not obj.license_expires_at:
            return None
        from django.utils import timezone
        delta = obj.license_expires_at - timezone.now()
        return max(0, delta.days)


# ==========================================================
#                   反馈相关序列化器
# ==========================================================

class FeedbackCreateSerializer(serializers.ModelSerializer):
    """创建反馈的序列化器"""
    
    class Meta:
        model = Feedback
        fields = [
            'feedback_type',
            'content',
            'rating',
            'contact_email',
        ]
    
    def validate_content(self, value):
        """验证反馈内容"""
        if not value or not value.strip():
            raise serializers.ValidationError('反馈内容不能为空')
        if len(value) > 2000:
            raise serializers.ValidationError('反馈内容不能超过2000字符')
        return value.strip()
    
    def validate_rating(self, value):
        """验证评分"""
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError('评分必须在1-5之间')
        return value
    
    def validate_contact_email(self, value):
        """验证联系邮箱格式"""
        if value:
            value = value.strip().lower()
        return value


class FeedbackListSerializer(serializers.ModelSerializer):
    """反馈列表序列化器（用于管理员查看）"""
    
    user_email = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_feedback_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    submitter_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = Feedback
        fields = [
            'id',
            'user_email',
            'submitter_display',
            'feedback_type',
            'type_display',
            'content',
            'rating',
            'status',
            'status_display',
            'created_at',
            'has_reply',
        ]
    
    def get_user_email(self, obj):
        """获取用户邮箱"""
        if obj.user:
            return obj.user.email
        elif obj.contact_email:
            return obj.contact_email
        return None


class FeedbackDetailSerializer(serializers.ModelSerializer):
    """反馈详情序列化器"""
    
    user_email = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_feedback_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    replied_by_email = serializers.SerializerMethodField()
    submitter_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = Feedback
        fields = [
            'id',
            'user',
            'user_email',
            'submitter_display',
            'feedback_type',
            'type_display',
            'content',
            'rating',
            'contact_email',
            'status',
            'status_display',
            'user_agent',
            'ip_address',
            'created_at',
            'updated_at',
            'admin_reply',
            'replied_at',
            'replied_by',
            'replied_by_email',
            'is_resolved',
            'has_reply',
        ]
        read_only_fields = [
            'id',
            'user',
            'status',
            'created_at',
            'updated_at',
            'admin_reply',
            'replied_at',
            'replied_by',
        ]
    
    def get_user_email(self, obj):
        """获取用户邮箱"""
        return obj.user.email if obj.user else None
    
    def get_replied_by_email(self, obj):
        """获取回复人邮箱"""
        return obj.replied_by.email if obj.replied_by else None


class FeedbackReplySerializer(serializers.Serializer):
    """管理员回复反馈序列化器"""
    
    reply = serializers.CharField(required=True, max_length=2000)
    status = serializers.ChoiceField(
        choices=Feedback.STATUS_CHOICES,
        required=False
    )
    
    def validate_reply(self, value):
        """验证回复内容"""
        if not value or not value.strip():
            raise serializers.ValidationError('回复内容不能为空')
        return value.strip()


class FeedbackUpdateStatusSerializer(serializers.Serializer):
    """更新反馈状态序列化器"""
    
    status = serializers.ChoiceField(
        choices=Feedback.STATUS_CHOICES,
        required=True
    )