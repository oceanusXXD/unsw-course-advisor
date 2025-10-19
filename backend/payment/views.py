# payment_views.py
import stripe
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from email_utils import send_license_email
stripe.api_key = settings.STRIPE_SECRET_KEY

PRICING = {
    'monthly': {
        'price_id': 'price_xxxxx',  # Stripe 价格 ID
        'amount': 999,  # $9.99
        'duration_days': 30,
    },
    'yearly': {
        'price_id': 'price_yyyyy',
        'amount': 9900,  # $99.00
        'duration_days': 365,
    },
}

@api_view(['POST'])
def create_checkout_session(request):
    """创建 Stripe 支付会话"""
    plan = request.data.get('plan', 'monthly')
    email = request.data.get('email')
    
    if plan not in PRICING:
        return Response({'error': 'Invalid plan'}, status=400)
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': PRICING[plan]['price_id'],
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{settings.FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{settings.FRONTEND_URL}/cancel',
            customer_email=email,
            metadata={
                'plan': plan,
                'duration_days': PRICING[plan]['duration_days'],
            }
        )
        
        return Response({'checkout_url': session.url})
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def stripe_webhook(request):
    """处理 Stripe 支付成功回调"""
    import json
    
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return Response({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return Response({'error': 'Invalid signature'}, status=400)
    
    # 处理支付成功事件
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # 创建许可证
        from .views import create_license
        from datetime import timedelta
        from django.utils import timezone
        
        email = session['customer_email']
        duration_days = int(session['metadata']['duration_days'])
        
        license_obj = License.objects.create(
            license_key=License.generate_license_key(),
            user_email=email,
            expires_at=timezone.now() + timedelta(days=duration_days),
            max_devices=2,
        )
        
        # 发送许可证邮件
        send_license_email(email, license_obj.license_key)
        
        print(f"✅ 为 {email} 创建许可证: {license_obj.license_key}")
    
    return Response({'status': 'success'})


