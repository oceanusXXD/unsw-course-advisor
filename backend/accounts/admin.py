from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import User, FileKey
# check

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """用户管理（包含许可证信息）"""
    
    list_display = (
        'email', 'username', 'is_active', 'is_staff',
        'license_status_display', 'license_expires_display', 'date_joined'
    )
    list_filter = (
        'is_active', 'is_staff', 'is_superuser',
        'license_active', 'date_joined'
    )
    search_fields = ('email', 'username', 'license_key', 'device_id')
    ordering = ('-date_joined',)
    
    fieldsets = (
        ('基本信息', {
            'fields': ('email', 'username', 'password')
        }),
        ('权限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('许可证信息', {
            'fields': (
                'license_key', 'device_id', 'license_active',
                'license_activated_at', 'license_expires_at'
            ),
            'classes': ('collapse',)
        }),
        ('敏感信息', {
            'fields': ('user_key',),
            'classes': ('collapse',),
            'description': '用户密钥是敏感信息，请勿随意修改'
        }),
        ('时间信息', {
            'fields': ('date_joined', 'last_login'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')
    
    def license_status_display(self, obj):
        """许可证状态显示"""
        if not obj.license_active:
            return format_html(
                '<span style="color: gray;">未激活</span>'
            )
        if obj.license_expires_at and timezone.now() > obj.license_expires_at:
            return format_html(
                '<span style="color: red; font-weight: bold;">已过期</span>'
            )
        return format_html(
            '<span style="color: green; font-weight: bold;">✓ 已激活</span>'
        )
    license_status_display.short_description = '许可证状态'
    
    def license_expires_display(self, obj):
        """许可证过期时间显示"""
        if not obj.license_expires_at:
            return '-'
        
        now = timezone.now()
        if now > obj.license_expires_at:
            delta = now - obj.license_expires_at
            return format_html(
                '<span style="color: red;">已过期 {} 天</span>',
                delta.days
            )
        else:
            delta = obj.license_expires_at - now
            if delta.days <= 30:
                color = 'orange'
            else:
                color = 'green'
            return format_html(
                '<span style="color: {};">剩余 {} 天</span>',
                color, delta.days
            )
    license_expires_display.short_description = '许可证过期时间'
    
    actions = ['activate_license', 'deactivate_license']
    
    def activate_license(self, request, queryset):
        """批量激活许可证"""
        updated = queryset.update(license_active=True)
        self.message_user(request, f'成功激活 {updated} 个用户的许可证')
    activate_license.short_description = '激活选中用户的许可证'
    
    def deactivate_license(self, request, queryset):
        """批量停用许可证"""
        updated = queryset.update(license_active=False)
        self.message_user(request, f'成功停用 {updated} 个用户的许可证')
    deactivate_license.short_description = '停用选中用户的许可证'


@admin.register(FileKey)
class FileKeyAdmin(admin.ModelAdmin):
    """文件密钥管理"""
    
    list_display = (
        'file_id_short', 'creator_user', 'creator_device_id',
        'created_at', 'key_preview'
    )
    list_filter = ('created_at', 'creator_user')
    search_fields = ('file_id', 'creator_device_id', 'creator_user__email')
    readonly_fields = ('file_id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('文件信息', {
            'fields': ('file_id', 'creator_user', 'creator_device_id')
        }),
        ('加密数据', {
            'fields': ('nonce', 'tag', 'encrypted_key'),
            'classes': ('collapse',),
            'description': '这些是加密后的密钥数据，请勿随意修改'
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def file_id_short(self, obj):
        """文件ID简写显示"""
        return f"{obj.file_id[:8]}..."
    file_id_short.short_description = '文件ID'
    
    def key_preview(self, obj):
        """密钥预览"""
        if obj.encrypted_key and len(obj.encrypted_key) > 20:
            return f"{obj.encrypted_key[:20]}..."
        return obj.encrypted_key or '-'
    key_preview.short_description = '加密密钥预览'
    
    def has_add_permission(self, request):
        """禁止手动添加（应通过加密流程创建）"""
        return False