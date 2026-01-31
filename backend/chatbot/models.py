# chatbot/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone

class UserMemory(models.Model):
    """
    存储用户的完整记忆结构，替代原有的 JSON 文件。
    """
    # 关联到 Django 的 User 模型
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True, # 直接使用 user_id 作为主键，保证一对一
        related_name='memory'
    )

    # 存储长时程总结
    long_term_summary = models.TextField(blank=True, default="")

    # 存储最近的对话记录。JSONField 是存储 JSON 结构的完美选择。
    # Django 会自动处理序列化和反序列化。
    recent_conversations = models.JSONField(default=list, blank=True)

    # 存储归档总结的元数据
    archived_summaries = models.JSONField(default=list, blank=True)

    # 记录最后更新时间，用于调试和潜在的清理任务
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Memory for {self.user.email or self.user.id}"

    class Meta:
        verbose_name = "User Memory"
        verbose_name_plural = "User Memories"