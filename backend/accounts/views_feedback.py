# backend/accounts/views_feedback.py

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone

from .models import Feedback
from .serializers import (
    FeedbackDetailSerializer,
    FeedbackCreateSerializer,
    FeedbackListSerializer,
)

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class FeedbackSubmitView(APIView):
    """
    提交反馈
    
    POST /api/accounts/feedback/
    {
        "feedback_type": "bug",  // bug | feature | suggestion | other
        "content": "反馈内容",
        "rating": 4,  // 可选：1-5
        "contact_email": "user@example.com"  // 可选
    }
    """
    permission_classes = [AllowAny]  # 允许匿名提交
    
    def post(self, request):
        try:
            logger.info(f"[Feedback] Received feedback submission: {request.data}")
            
            serializer = FeedbackCreateSerializer(data=request.data)
            if not serializer.is_valid():
                logger.warning(f"[Feedback] Validation error: {serializer.errors}")
                return Response({
                    'status': 'error',
                    'error': serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 保存反馈
            feedback = serializer.save(
                user=request.user if request.user.is_authenticated else None,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=get_client_ip(request),
            )
            
            logger.info(f"[Feedback] Feedback #{feedback.id} created successfully")
            
            # 可选：发送通知邮件给管理员
            # send_feedback_notification(feedback)
            
            return Response({
                'status': 'ok',
                'message': '感谢您的反馈！我们会尽快处理。',
                'feedback_id': feedback.id,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"[Feedback] Error submitting feedback: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': '提交反馈失败，请稍后重试',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FeedbackPagination(PageNumberPagination):
    """反馈分页器"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class FeedbackListView(APIView):
    """
    获取反馈列表（仅管理员）
    
    GET /api/accounts/feedback/list/?page=1&status=pending&type=bug
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        try:
            # 获取查询参数
            feedback_status = request.GET.get('status', None)
            feedback_type = request.GET.get('type', None)
            
            # 构建查询
            queryset = Feedback.objects.all()
            
            if feedback_status:
                queryset = queryset.filter(status=feedback_status)
            
            if feedback_type:
                queryset = queryset.filter(feedback_type=feedback_type)
            
            # 分页
            paginator = FeedbackPagination()
            page = paginator.paginate_queryset(queryset, request)
            
            if page is not None:
                serializer = FeedbackListSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = FeedbackListSerializer(queryset, many=True)
            return Response({
                'status': 'ok',
                'feedbacks': serializer.data,
            })
            
        except Exception as e:
            logger.error(f"[Feedback] Error listing feedbacks: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': '获取反馈列表失败',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FeedbackDetailView(APIView):
    """
    获取反馈详情（管理员）或用户自己的反馈
    
    GET /api/accounts/feedback/<id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, feedback_id):
        try:
            feedback = Feedback.objects.get(id=feedback_id)
            
            # 权限检查：管理员或反馈创建者
            if not (request.user.is_staff or feedback.user == request.user):
                return Response({
                    'status': 'error',
                    'error': '无权访问此反馈',
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = FeedbackDetailSerializer(feedback)
            return Response({
                'status': 'ok',
                'feedback': serializer.data,
            })
            
        except Feedback.DoesNotExist:
            return Response({
                'status': 'error',
                'error': '反馈不存在',
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[Feedback] Error getting feedback: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': '获取反馈失败',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FeedbackReplyView(APIView):
    """
    管理员回复反馈
    
    POST /api/accounts/feedback/<id>/reply/
    {
        "reply": "回复内容",
        "status": "resolved"  // 可选：更新状态
    }
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request, feedback_id):
        try:
            feedback = Feedback.objects.get(id=feedback_id)
            
            reply_content = request.data.get('reply', '').strip()
            if not reply_content:
                return Response({
                    'status': 'error',
                    'error': '回复内容不能为空',
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 更新反馈
            feedback.admin_reply = reply_content
            feedback.replied_at = timezone.now()
            feedback.replied_by = request.user
            
            # 可选：更新状态
            new_status = request.data.get('status')
            if new_status and new_status in dict(Feedback.STATUS_CHOICES):
                feedback.status = new_status
            
            feedback.save()
            
            logger.info(f"[Feedback] Admin {request.user.email} replied to feedback #{feedback_id}")
            
            # 可选：发送邮件通知用户
            # send_reply_notification(feedback)
            
            serializer = FeedbackDetailSerializer(feedback)
            return Response({
                'status': 'ok',
                'message': '回复成功',
                'feedback': serializer.data,
            })
            
        except Feedback.DoesNotExist:
            return Response({
                'status': 'error',
                'error': '反馈不存在',
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[Feedback] Error replying to feedback: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': '回复失败',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FeedbackUpdateStatusView(APIView):
    """
    更新反馈状态（管理员）
    
    PATCH /api/accounts/feedback/<id>/status/
    {
        "status": "reviewing"  // pending | reviewing | resolved | closed
    }
    """
    permission_classes = [IsAdminUser]
    
    def patch(self, request, feedback_id):
        try:
            feedback = Feedback.objects.get(id=feedback_id)
            
            new_status = request.data.get('status')
            if not new_status:
                return Response({
                    'status': 'error',
                    'error': '状态不能为空',
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if new_status not in dict(Feedback.STATUS_CHOICES):
                return Response({
                    'status': 'error',
                    'error': '无效的状态值',
                }, status=status.HTTP_400_BAD_REQUEST)
            
            feedback.status = new_status
            feedback.save()
            
            logger.info(f"[Feedback] Feedback #{feedback_id} status updated to {new_status}")
            
            return Response({
                'status': 'ok',
                'message': '状态更新成功',
            })
            
        except Feedback.DoesNotExist:
            return Response({
                'status': 'error',
                'error': '反馈不存在',
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[Feedback] Error updating feedback status: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': '更新状态失败',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MyFeedbacksView(APIView):
    """
    获取当前用户的反馈列表
    
    GET /api/accounts/feedback/my/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            feedbacks = Feedback.objects.filter(user=request.user).order_by('-created_at')
            serializer = FeedbackListSerializer(feedbacks, many=True)
            
            return Response({
                'status': 'ok',
                'feedbacks': serializer.data,
            })
            
        except Exception as e:
            logger.error(f"[Feedback] Error getting user feedbacks: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': '获取反馈列表失败',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)