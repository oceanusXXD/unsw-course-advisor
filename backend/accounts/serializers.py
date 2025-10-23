from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User
# check
class RegisterSerializer(serializers.ModelSerializer):
    """用户注册序列化器"""
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ('email', 'username', 'password')

    def validate_email(self, value):
        """验证邮箱唯一性"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("该邮箱已被注册")
        return value

    def create(self, validated_data):
        """创建用户（默认未激活许可证）"""
        user = User.objects.create_user(**validated_data)
        # 用户创建时，许可证字段保持默认值（未激活）
        return user


class LoginSerializer(serializers.Serializer):
    """用户登录序列化器"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError("邮箱或密码错误")
        if not user.is_active:
            raise serializers.ValidationError("账户未激活")
        return {'user': user}


class LicenseActivateSerializer(serializers.Serializer):
    """许可证激活序列化器"""
    device_id = serializers.CharField(
        max_length=128, 
        required=True,
        help_text="设备唯一标识符"
    )
    expires_in_days = serializers.IntegerField(
        required=False,
        default=365,
        min_value=1,
        max_value=3650,
        help_text="许可证有效期（天），默认365天"
    )


class LicenseInfoSerializer(serializers.ModelSerializer):
    """许可证信息序列化器（不包含敏感字段）"""
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
        """获取许可证是否有效"""
        return obj.is_license_valid

    def get_days_until_expiry(self, obj):
        """获取距离过期天数"""
        if not obj.license_expires_at:
            return None
        from django.utils import timezone
        delta = obj.license_expires_at - timezone.now()
        return max(0, delta.days)


class UserDetailSerializer(serializers.ModelSerializer):
    """用户详情序列化器"""
    license = LicenseInfoSerializer(source='*', read_only=True)

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
        read_only_fields = ('id', 'date_joined', 'last_login')


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码序列化器"""
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=6)
    
    def validate_new_password(self, value):
        """验证新密码强度（可选）"""
        if len(value) < 6:
            raise serializers.ValidationError("密码长度至少6位")
        return value