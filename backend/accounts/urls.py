from django.urls import path
from . import views_login, views_license,views_social_login
from . import views_feedback 
urlpatterns = [
    # 用户相关
    path("register/", views_login.RegisterView.as_view()),
    path("login/", views_login.LoginView.as_view()),
    path("logout/", views_login.LogoutView.as_view()),
    path("me/", views_login.CurrentUserView.as_view()),
    path("change-password/", views_login.ChangePasswordView.as_view()),
    path("delete/", views_login.DeleteUserView.as_view()),

    # 第三方登录
    path("google/", views_social_login.GoogleLoginView.as_view()),
    path("github/", views_social_login.GitHubLoginView.as_view()),
    path("outlook/", views_social_login.OutlookLoginView.as_view()),

    # Token 刷新
    path("token/refresh/", views_social_login.CustomTokenRefreshView.as_view()),

    # 许可证 + 系统数据相关
    path("license/activate/", views_license.ActivateLicenseView.as_view()),
    path("license/validate/", views_license.ValidateLicenseView.as_view()),
    path("license/my/", views_license.GetMyLicenseView.as_view()),
    path("license/file-key/", views_license.GetFileDecryptKeyView.as_view()),
    path("license/course-map/", views_license.GetCourseMapView.as_view()),
    # 反馈相关
    path('feedback/', views_feedback.FeedbackSubmitView.as_view(), name='feedback-submit'),
    path('feedback/list/', views_feedback.FeedbackListView.as_view(), name='feedback-list'),
    path('feedback/my/', views_feedback.MyFeedbacksView.as_view(), name='my-feedbacks'),
    path('feedback/<int:feedback_id>/', views_feedback.FeedbackDetailView.as_view(), name='feedback-detail'),
    path('feedback/<int:feedback_id>/reply/', views_feedback.FeedbackReplyView.as_view(), name='feedback-reply'),
    path('feedback/<int:feedback_id>/status/', views_feedback.FeedbackUpdateStatusView.as_view(), name='feedback-update-status'),
]
