"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
api_patterns = [
    path("admin/", admin.site.urls),
    path("chatbot/", include("chatbot.urls")),
    path('extension/', include('extension.urls')),
    path('accounts/', include('accounts.urls')),
]

urlpatterns = [
    path("api/", include(api_patterns)),
]

# 开发环境下提供媒体文件访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 自定义后台标题（可选）
admin.site.site_header = "课程顾问系统管理后台"
admin.site.site_title = "管理后台"
admin.site.index_title = "欢迎使用管理后台"