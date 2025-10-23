# backend/accounts/email_utils.py
from django.core.mail import send_mail
from django.conf import settings
# Unused​
def send_license_email(email: str, license_key: str):
    """发送许可证密钥邮件"""
    subject = "您的课程顾问系统许可证密钥"
    message = f"""
亲爱的用户，

感谢您的购买！

您的许可证密钥是：
{license_key}

请妥善保管此密钥，您需要使用它来在应用内激活您的许可证。

祝使用愉快！
"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )