# models.py
from django.db import models
from django.utils import timezone
import secrets
import hashlib

class License(models.Model):
    """许可证模型"""
    STATUS_CHOICES = [
        ('active', '激活'),
        ('expired', '过期'),
        ('revoked', '已撤销'),
    ]
    
    license_key = models.CharField(max_length=64, unique=True, db_index=True)
    user_email = models.EmailField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    max_devices = models.IntegerField(default=2)  # 最多激活设备数
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def is_valid(self):
        """检查许可证是否有效"""
        return (
            self.status == 'active' and
            self.expires_at > timezone.now()
        )
    
    def can_activate_device(self):
        """检查是否还能激活新设备"""
        return self.activations.count() < self.max_devices
    
    @staticmethod
    def generate_license_key():
        """生成许可证密钥（格式：XXXX-XXXX-XXXX-XXXX）"""
        raw = secrets.token_hex(16)
        return '-'.join([raw[i:i+4] for i in range(0, 16, 4)]).upper()


class DeviceActivation(models.Model):
    """设备激活记录"""
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='activations')
    device_id = models.CharField(max_length=128)  # 设备指纹
    decrypt_key = models.CharField(max_length=128)  # 该设备的解密密钥
    activated_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('license', 'device_id')