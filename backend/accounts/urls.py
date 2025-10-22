from django.urls import path
from .views import (
    # 用户认证
    RegisterView,
    LoginView,
    CurrentUserView,
    LogoutView,
    ChangePasswordView,
    #StripeWebhookView,
    # 许可证管理
    ActivateLicenseView,
    ValidateLicenseView,
    GetMyLicenseView,
    GetFileDecryptKeyView,
    GetCourseMapView
)

app_name = 'accounts'

urlpatterns = [
    # ========== 用户认证接口 ==========
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    # ========== 许可证管理接口 ==========
    path('license/activate/', ActivateLicenseView.as_view(), name='license-activate'),
    path('license/validate/', ValidateLicenseView.as_view(), name='license-validate'),
    path('license/my/', GetMyLicenseView.as_view(), name='my-license'),
    path('license/file-key/', GetFileDecryptKeyView.as_view(), name='file-decrypt-key'),
    # ========== 支付认证接口 ==========
    #path('stripe-webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    
    # ========== 课程映射接口 ==========
    path("get_course/", GetCourseMapView.as_view(), name="get_course"),
]