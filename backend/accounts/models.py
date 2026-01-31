# 文件路径: unsw-course-advisor\backend\accounts\models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

# ==========================================================
#                  自定义用户管理器
# ==========================================================

class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        """
        私有创建用户方法，处理通用逻辑，防止代码重复。
        """
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        # 超级用户默认拥有激活的、永不过期的许可证
        extra_fields.setdefault('license_active', True)
        extra_fields.setdefault('license_expires_at', None)

        return self._create_user(email, password, **extra_fields)

# ==========================================================
#                       用户模型
# ==========================================================

class User(AbstractBaseUser, PermissionsMixin):
    """
    自定义用户模型，集成了许可证管理功能。
    针对 MySQL 进行了字段长度和类型的优化。
    """
    # --- 核心认证字段 ---
    email = models.EmailField(
        max_length=254,
        unique=True, 
        verbose_name='邮箱'
    )
    username = models.CharField(
        max_length=150,
        blank=True, 
        verbose_name='用户名 (可选)'
    )
    
    # --- 状态与权限 ---
    is_active = models.BooleanField(
        default=True, 
        verbose_name='账号激活状态',
        help_text='Designates whether this user should be treated as active.'
    )
    is_staff = models.BooleanField(
        default=False, 
        verbose_name='后台访问权限',
        help_text='Designates whether the user can log into this admin site.'
    )
    date_joined = models.DateTimeField(
        default=timezone.now, 
        verbose_name='注册时间'
    )

    # --- 许可证相关字段 ---
    license_key = models.CharField(
        max_length=100,
        unique=True, 
        blank=True, 
        null=True,
        verbose_name='许可证密钥'
    )
    user_key = models.TextField(
        blank=True, 
        null=True,
        verbose_name='用户密钥',
        help_text='Base64编码的用户密钥（敏感信息）'
    )
    device_id = models.CharField(
        max_length=255,
        blank=True, 
        null=True,
        db_index=True,
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
        verbose_name='许可证到期时间'
    )
    license_active = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='许可证激活状态'
    )

    # --- Django 配置 ---
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'accounts_user'
        verbose_name = '用户'
        verbose_name_plural = '用户'
        indexes = [
            models.Index(fields=['license_key']),
        ]

    def __str__(self):
        return self.email

    @property
    def is_license_valid(self):
        """
        检查用户的许可证当前是否有效（属性方法）。
        """
        if not self.license_active:
            return False
        if self.license_expires_at and timezone.now() > self.license_expires_at:
            return False
        return True

    def verify_license_validity(self):
        """
        验证许可证有效性，返回 (is_valid: bool, reason: str) 元组。
        
        Returns:
            tuple: (是否有效, 原因说明)
        """
        if not self.license_active:
            return False, "许可证未激活"
        
        if not self.license_key:
            return False, "许可证密钥不存在"
        
        if self.license_expires_at:
            if timezone.now() > self.license_expires_at:
                return False, "许可证已过期"
        
        return True, "许可证有效"

    def get_license_remaining_days(self):
        """
        计算许可证剩余天数。
        
        Returns:
            int | None: 剩余天数，如果未设置过期时间或已过期返回 None
        """
        if not self.license_expires_at:
            return None  # 永久许可证或未设置过期时间
        
        remaining = self.license_expires_at - timezone.now()
        if remaining.total_seconds() < 0:
            return 0  # 已过期
        
        return remaining.days

    def clean(self):
        """
        自定义模型验证逻辑。
        """
        super().clean()
        self.email = self.email.lower()

# ==========================================================
#                      文件密钥模型
# ==========================================================

class FileKey(models.Model):
    """
    存储与文件相关的加密密钥信息。
    """
    file_id = models.CharField(
        max_length=64, 
        unique=True, 
        primary_key=True,
        verbose_name='文件ID'
    )
    nonce = models.TextField(verbose_name='Nonce (base64)')
    tag = models.TextField(verbose_name='Tag (base64)')
    encrypted_key = models.TextField(verbose_name='加密的文件密钥 (base64)')
    
    creator_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_files',
        verbose_name='创建者'
    )
    creator_device_id = models.CharField(
        max_length=255,
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
        db_table = 'accounts_filekey'
        verbose_name = '文件密钥'
        verbose_name_plural = '文件密钥'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['creator_user', 'created_at']), 
        ]

    def __str__(self):
        return f"FileKey for file {self.file_id[:8]}..."


# ==========================================================
#                      用户反馈模型
# ==========================================================

class Feedback(models.Model):
    """
    用户反馈模型
    支持匿名反馈和已登录用户反馈
    """
    
    FEEDBACK_TYPES = [
        ('bug', 'Bug 报告'),
        ('feature', '功能建议'),
        ('suggestion', '改进建议'),
        ('other', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('reviewing', '审核中'),
        ('resolved', '已解决'),
        ('closed', '已关闭'),
    ]
    
    # --- 基础字段 ---
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedbacks',
        verbose_name='提交用户',
        help_text='提交反馈的用户（可为空，支持匿名反馈）'
    )
    
    feedback_type = models.CharField(
        max_length=20,
        choices=FEEDBACK_TYPES,
        default='suggestion',
        verbose_name='反馈类型'
    )
    
    content = models.TextField(
        verbose_name='反馈内容',
        help_text='用户提交的反馈内容'
    )
    
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        verbose_name='评分',
        help_text='用户评分（1-5星）'
    )
    
    contact_email = models.EmailField(
        max_length=254,
        null=True,
        blank=True,
        verbose_name='联系邮箱',
        help_text='用户留下的联系邮箱（可选）'
    )
    
    # --- 状态管理 ---
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='处理状态'
    )
    
    # --- 元数据 ---
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name='用户代理',
        help_text='用户浏览器信息'
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP 地址',
        help_text='提交反馈时的 IP 地址'
    )
    
    # --- 时间戳 ---
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='创建时间'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )
    
    # --- 管理员回复 ---
    admin_reply = models.TextField(
        null=True,
        blank=True,
        verbose_name='管理员回复',
        help_text='管理员对反馈的回复'
    )
    
    replied_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='回复时间'
    )
    
    replied_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replied_feedbacks',
        verbose_name='回复人',
        help_text='回复该反馈的管理员'
    )
    
    class Meta:
        db_table = 'accounts_feedback'
        verbose_name = '用户反馈'
        verbose_name_plural = '用户反馈'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['feedback_type']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        user_display = self.user.email if self.user else (
            self.contact_email if self.contact_email else 'Anonymous'
        )
        return f'{self.get_feedback_type_display()} from {user_display} at {self.created_at.strftime("%Y-%m-%d %H:%M")}'
    
    @property
    def is_resolved(self):
        """是否已解决"""
        return self.status in ['resolved', 'closed']
    
    @property
    def has_reply(self):
        """是否有管理员回复"""
        return bool(self.admin_reply)
    
    @property
    def submitter_display(self):
        """获取提交者显示名称"""
        if self.user:
            return self.user.email
        elif self.contact_email:
            return f'{self.contact_email} (游客)'
        return '匿名用户'