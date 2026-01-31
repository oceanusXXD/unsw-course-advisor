# ======================== 依赖导入 ========================
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.microsoft.views import MicrosoftGraphOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.http import JsonResponse
from django.conf import settings
import logging
import requests
from .models import User

logger = logging.getLogger(__name__)

def get_tokens_for_user(user):
    """为用户生成 JWT tokens"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

# 修改：统一 JWT 响应格式，确保 username 不为空
def _normalize_jwt_response(resp):
    try:
        data = dict(resp.data) if hasattr(resp, "data") else None
    except Exception:
        data = None

    if not isinstance(data, dict):
        return resp

    access = data.get("access")
    refresh = data.get("refresh")
    if not access or not refresh:
        return resp

    # tokens 字段对齐你现有接口
    if "tokens" not in data:
        data["tokens"] = {"access": access, "refresh": refresh}

    # 修改：若没有 user，则尝试从 access 里解析 user_id 并查库补全
    if "user" not in data:
        try:
            token = AccessToken(access)
            user_id_claim = getattr(settings, "SIMPLE_JWT", {}).get("USER_ID_CLAIM", "user_id")
            user_id = token[user_id_claim]
            u = User.objects.filter(id=user_id).first()
            if u:
                # 确保 username 不为空
                username = u.username
                if not username or username.strip() == '':
                    username = u.email.split('@')[0] if u.email else f'user_{u.id}'
                    # 更新数据库
                    try:
                        u.username = username
                        u.save(update_fields=['username'])
                        logger.info(f"[JWT] Updated username for user {u.id}: {username}")
                    except Exception as e:
                        logger.warning(f"[JWT] Failed to update username: {e}")
                
                data["user"] = {
                    "id": u.id,
                    "email": u.email,
                    "username": username
                }
                logger.info(f"[JWT] Normalized user data: {data['user']}")
        except Exception as e:
            logger.error(f"[JWT] Failed to normalize user: {e}")

    resp.data = data
    return resp

# ======================== 社交登录：Google ========================
# ======================== 社交登录：Google ========================
class GoogleLoginView(SocialLoginView):
    permission_classes = [AllowAny]
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        logger.info(f"[BACKEND] 1. GoogleLoginView received data: {request.data}")

        if hasattr(request.data, '_mutable'):
            request.data._mutable = True

        code = request.data.get('code')
        logger.info(f"[BACKEND] 2. Extracted code: {code}")

        if code:
            logger.info("[BACKEND] 3. Code found, preparing to exchange...")
            try:
                provider_config = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']
                client_id = provider_config.get('client_id')
                client_secret = provider_config.get('secret')

                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
                redirect_uri = f"{frontend_url}/auth/google/callback"

                logger.info(f"[BACKEND] 4. Using Client ID: {client_id[:10] + '...' if client_id else 'None'}")
                logger.info(f"[BACKEND] 5. Using Dynamic Callback URL: {redirect_uri}")

                if not client_id or not client_secret:
                    logger.critical("Google credentials not configured in settings.py.")
                    return JsonResponse({'error': 'Server configuration error: Google credentials missing.'}, status=500)

                token_url = 'https://oauth2.googleapis.com/token'
                payload = {
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                }

                response = requests.post(token_url, data=payload, timeout=10)
                response_data = response.json()
                
                # 新增：打印 Google 响应
                logger.info(f"[BACKEND] 6. Google token response: status={response.status_code}, data={response_data}")
                
                if response.status_code != 200:
                    return JsonResponse({'error': response_data.get('error_description', 'Google exchange failed')}, status=response.status_code)

                access_token = response_data.get('access_token')
                request.data.pop('code', None)
                request.data['access_token'] = access_token

            except requests.RequestException as e:
                logger.error(f"Network error during Google code exchange: {e}", exc_info=True)
                return JsonResponse({'error': 'Network error when contacting Google'}, status=502)
            except Exception as e:
                logger.error(f"Error during Google code exchange: {e}", exc_info=True)
                return JsonResponse({'error': str(e)}, status=500)

        logger.info(f"[BACKEND] 7. Calling super().post() with access_token={request.data.get('access_token', 'None')[:20]}...")
        
        # 新增：详细的错误捕获
        try:
            resp = super().post(request, *args, **kwargs)
            
            logger.info(f"[BACKEND] 8. super().post() returned status={resp.status_code}")
            logger.info(f"[BACKEND] 9. super().post() data={resp.data}")

            # 如果返回非 200，记录详细错误
            if resp.status_code != 200:
                logger.error(f"[BACKEND] Google login failed: {resp.data}")
            
            return _normalize_jwt_response(resp)
            
        except Exception as e:
            logger.error(f"[BACKEND] Exception in super().post(): {type(e).__name__}: {e}", exc_info=True)
            
            # 尝试获取详细信息
            error_detail = str(e)
            if hasattr(e, 'detail'):
                error_detail = e.detail
                logger.error(f"[BACKEND] Exception detail: {error_detail}")
            
            # 兜底方案：直接通过 Google API 获取用户信息
            access_token = request.data.get('access_token')
            if access_token:
                logger.info("[BACKEND] Attempting fallback: fetching user from Google API...")
                try:
                    google_user_response = requests.get(
                        'https://www.googleapis.com/oauth2/v2/userinfo',
                        headers={'Authorization': f'Bearer {access_token}'},
                        timeout=10
                    )
                    
                    if google_user_response.status_code == 200:
                        google_user = google_user_response.json()
                        logger.info(f"[BACKEND] Google user info: {google_user}")
                        
                        email = google_user.get('email')
                        if email:
                            # 创建或获取用户
                            user, created = User.objects.get_or_create(
                                email=email,
                                defaults={
                                    'username': email.split('@')[0],
                                    'is_active': True,
                                }
                            )
                            
                            logger.info(f"[BACKEND] User {'created' if created else 'found'}: {user.email}")
                            
                            # 确保 username 不为空
                            if not user.username or user.username.strip() == '':
                                user.username = email.split('@')[0]
                                user.save(update_fields=['username'])
                            
                            tokens = get_tokens_for_user(user)
                            return Response({
                                'access': tokens['access'],
                                'refresh': tokens['refresh'],
                                'user': {
                                    'id': user.id,
                                    'email': user.email,
                                    'username': user.username
                                },
                                'tokens': tokens
                            }, status=status.HTTP_200_OK)
                            
                except requests.RequestException as google_err:
                    logger.error(f"[BACKEND] Error querying Google user info: {google_err}", exc_info=True)
                except Exception as google_err:
                    logger.error(f"[BACKEND] Unexpected error in fallback: {google_err}", exc_info=True)
            
            # 如果兜底也失败，返回详细错误
            return JsonResponse({
                'error': 'Google authentication failed',
                'detail': error_detail,
                'type': type(e).__name__
            }, status=400)

# ======================== 社交登录：GitHub ========================
class GitHubLoginView(SocialLoginView):
    permission_classes = [AllowAny]
    adapter_class = GitHubOAuth2Adapter
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        logger.info(f"[BACKEND] 1. GitHubLoginView received data: {request.data}")

        if hasattr(request.data, '_mutable'):
            request.data._mutable = True

        code = request.data.get('code')
        logger.info(f"[BACKEND] 2. Extracted code: {code}")

        if code:
            logger.info("[BACKEND] 3. Code found, preparing to exchange...")
            try:
                provider_config = settings.SOCIALACCOUNT_PROVIDERS['github']['APP']
                client_id = provider_config.get('client_id')
                client_secret = provider_config.get('secret')

                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
                redirect_uri = f"{frontend_url}/auth/github/callback"

                if not client_id or not client_secret:
                    logger.critical("GitHub credentials not configured in settings.py.")
                    return JsonResponse({'error': 'Server configuration error: GitHub credentials missing.'}, status=500)

                token_url = 'https://github.com/login/oauth/access_token'
                payload = {
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                }
                headers = {'Accept': 'application/json'}

                response = requests.post(token_url, data=payload, headers=headers, timeout=10)
                response_data = response.json()
                if response.status_code != 200 or 'access_token' not in response_data:
                    return JsonResponse({'error': response_data.get('error_description', 'GitHub exchange failed')}, status=response.status_code)

                access_token = response_data.get('access_token')
                request.data.pop('code', None)
                request.data['access_token'] = access_token

            except requests.RequestException as e:
                logger.error(f"Network error during GitHub code exchange: {e}", exc_info=True)
                return JsonResponse({'error': 'Network error when contacting GitHub'}, status=502)
            except Exception as e:
                logger.error(f"Error during GitHub code exchange: {e}", exc_info=True)
                return JsonResponse({'error': str(e)}, status=500)

        logger.info("[BACKEND] 9. Calling super().post() to finalize login...")
        try:
            resp = super().post(request, *args, **kwargs)
            return _normalize_jwt_response(resp)
        except Exception as e:
            # 兼容你原有的"多账户合并"兜底逻辑
            logger.error(f"[BACKEND] GitHubLoginView error: {type(e).__name__}: {e}")
            if "Multiple" in str(type(e).__name__) or "multiple" in str(e).lower():
                access_token = request.data.get('access_token')
                if access_token:
                    try:
                        github_user_response = requests.get(
                            'https://api.github.com/user',
                            headers={'Authorization': f'token {access_token}'},
                            timeout=10
                        )
                        if github_user_response.status_code == 200:
                            github_user = github_user_response.json()
                            email = github_user.get('email')

                            if not email:
                                github_emails_response = requests.get(
                                    'https://api.github.com/user/emails',
                                    headers={'Authorization': f'token {access_token}'},
                                    timeout=10
                                )
                                if github_emails_response.status_code == 200:
                                    emails = github_emails_response.json()
                                    primary_email = next((e['email'] for e in emails if e.get('primary')), None)
                                    email = primary_email or (emails[0]['email'] if emails else None)

                            if email:
                                user = User.objects.filter(email=email).first()
                                if user:
                                    # 修改：确保 username 不为空
                                    username = user.username
                                    if not username or username.strip() == '':
                                        username = user.email.split('@')[0] if user.email else f'user_{user.id}'
                                        try:
                                            user.username = username
                                            user.save(update_fields=['username'])
                                        except Exception:
                                            pass
                                    
                                    tokens = get_tokens_for_user(user)
                                    return Response({
                                        'access': tokens['access'],
                                        'refresh': tokens['refresh'],
                                        'user': {'id': user.id, 'email': user.email, 'username': username},
                                        'tokens': tokens
                                    }, status=status.HTTP_200_OK)
                    except requests.RequestException as github_err:
                        logger.error(f"[BACKEND] Error querying GitHub user info: {github_err}")
                    except Exception as github_err:
                        logger.error(f"[BACKEND] Unexpected error reading GitHub user info: {github_err}")
                return JsonResponse({'error': 'Multiple user accounts found for this email. Please contact support.'}, status=400)
            return JsonResponse({'error': 'Authentication failed'}, status=400)

# ======================== 社交登录：Outlook(Microsoft) ========================
class OutlookLoginView(SocialLoginView):
    permission_classes = [AllowAny]
    adapter_class = MicrosoftGraphOAuth2Adapter
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        logger.info(f"[BACKEND] 1. OutlookLoginView received data: {request.data}")

        if hasattr(request.data, '_mutable'):
            request.data._mutable = True

        code = request.data.get('code')
        logger.info(f"[BACKEND] 2. Extracted code: {code}")

        if code:
            logger.info("[BACKEND] 3. Code found, preparing to exchange...")
            try:
                provider_config = settings.SOCIALACCOUNT_PROVIDERS['microsoft']['APP']
                client_id = provider_config.get('client_id')
                client_secret = provider_config.get('secret')

                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
                redirect_uri = f"{frontend_url}/auth/outlook/callback"

                logger.info(f"[BACKEND] 4. Using Client ID: {client_id[:10] + '...' if client_id else 'None'}")
                logger.info(f"[BACKEND] 5. Using Dynamic Callback URL: {redirect_uri}")

                if not client_id or not client_secret:
                    logger.critical("Outlook credentials not configured in settings.py.")
                    return JsonResponse({'error': 'Server configuration error: Outlook credentials missing.'}, status=500)

                token_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
                payload = {
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                }

                response = requests.post(token_url, data=payload, timeout=10)
                response_data = response.json()
                if response.status_code != 200:
                    return JsonResponse({'error': response_data.get('error_description', 'Outlook exchange failed')}, status=response.status_code)

                access_token = response_data.get('access_token')
                request.data.pop('code', None)
                request.data['access_token'] = access_token

            except requests.RequestException as e:
                logger.error(f"Network error during Outlook code exchange: {e}", exc_info=True)
                return JsonResponse({'error': 'Network error when contacting Microsoft'}, status=502)
            except Exception as e:
                logger.error(f"Error during Outlook code exchange: {e}", exc_info=True)
                return JsonResponse({'error': str(e)}, status=500)

        logger.info("[BACKEND] 9. Calling super().post() to finalize login...")
        resp = super().post(request, *args, **kwargs)
        return _normalize_jwt_response(resp)

# ======================== Token 刷新 (保持不变) ========================
class CustomTokenRefreshView(TokenRefreshView):
    """刷新 access token"""
    def post(self, request, *args, **kwargs):
        logger.info(f"Token refresh attempt with data: {request.data}")
        return super().post(request, *args, **kwargs)