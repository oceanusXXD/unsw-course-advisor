# email_utils.py
from django.core.mail import send_mail
from django.conf import settings

def send_license_email(email: str, license_key: str):
    """发送许可证密钥邮件"""
    subject = "您的插件许可证密钥"
    
    message = f"""
亲爱的用户，

感谢您购买我们的插件！

您的许可证密钥是：
{license_key}

使用方法：
1. 下载插件：https://your-site.com/download
2. 打开插件，选择"激活许可证"
3. 输入上述密钥即可开始使用

如有任何问题，请联系：support@your-site.com

祝使用愉快！
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )