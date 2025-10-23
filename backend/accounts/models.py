from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
# check

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('邮箱不能为空')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('license_active', True)  # 超级用户默认激活许可证
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """用户模型（集成许可证管理）"""
    # 基础字段
    email = models.EmailField(unique=True, verbose_name='邮箱')
    username = models.CharField(max_length=100, blank=True, verbose_name='用户名')
    is_active = models.BooleanField(default=True, verbose_name='账号激活状态')
    is_staff = models.BooleanField(default=False, verbose_name='管理员')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='注册时间')

    # 许可证相关字段
    license_key = models.CharField(
        max_length=64, 
        unique=True, 
        blank=True, 
        null=True,
        verbose_name='许可证密钥'
    )
    user_key = models.TextField(
        blank=True, 
        null=True,
        verbose_name='用户密钥',
        help_text='base64编码的用户密钥（敏感信息）'
    )
    device_id = models.CharField(
        max_length=128, 
        blank=True, 
        null=True,
        verbose_name='设备ID'
    )
    license_activated_at = models.DateTimeField(
        blank=True, 
        null=True,
        verbose_name='许可证激活时间'
    )
    license_expires_at = models.DateTimeField(
        blank=True, 
        null=True,
        verbose_name='许可证过期时间'
    )
    license_active = models.BooleanField(
        default=False,
        verbose_name='许可证激活状态'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = '用户'
        indexes = [
            models.Index(fields=['license_key']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.email

    @property
    def is_license_valid(self):
        """检查许可证是否有效"""
        if not self.license_active:
            return False
        if self.license_expires_at and timezone.now() > self.license_expires_at:
            return False
        return True


class FileKey(models.Model):
    """文件密钥存储（独立表）"""
    file_id = models.CharField(
        max_length=64, 
        unique=True, 
        primary_key=True,
        verbose_name='文件ID'
    )
    nonce = models.TextField(verbose_name='Nonce（base64）')
    tag = models.TextField(verbose_name='Tag（base64）')
    encrypted_key = models.TextField(verbose_name='加密的文件密钥（base64）')
    creator_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_files',
        verbose_name='创建者'
    )
    creator_device_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name='创建设备ID'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        db_table = 'file_keys'
        verbose_name = '文件密钥'
        verbose_name_plural = '文件密钥'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['creator_user', 'created_at']),
        ]

    def __str__(self):
        return f"FileKey({self.file_id[:8]}...)"