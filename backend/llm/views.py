import hashlib
import ipaddress
import json
from contextlib import suppress

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.http import StreamingHttpResponse
from langchain_core.messages import AIMessage, HumanMessage
from openai import OpenAIError
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import BaseRenderer, BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from drf_spectacular.utils import OpenApiResponse, PolymorphicProxySerializer, extend_schema, extend_schema_view

from .chat_message_histories import DjangoChatMessageHistory
from .chat_service import ChatService
from .models import ChatMessage, ChatSession, ChatTurn
from .rag.pipeline import last_detail
from .serializers import (
    ChatCheckpointEventSerializer,
    ChatDeltaEventSerializer,
    ChatDoneEventSerializer,
    ChatErrorEventSerializer,
    ChatFinalizeResponseSerializer,
    ChatFinalizeSerializer,
    ChatMessageSerializer,
    ChatNonStreamResponseSerializer,
    ChatSessionSerializer,
    GuestChatDeltaEventSerializer,
    GuestChatDoneEventSerializer,
    GuestChatSerializer,
)


RECEIPT_SALT = "llm.chat-checkpoint.v1"
RECEIPT_MAX_AGE = 10 * 60


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "이 대화에는 더 최신 메시지가 있습니다."


class EventStreamRenderer(BaseRenderer):
    media_type = "text/event-stream"
    format = "sse"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data, ensure_ascii=False).encode()


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def course_meta():
    """이번 요청의 RAG 결과에서 지도·코스 저장에 쓸 것만 추린다 (코스 추천일 때만 값이 있다).

    코스를 짠 답이 아니면 None → done 에 아무것도 더 싣지 않는다.
    """
    d = last_detail()
    if not d or not (d.get("places") or d.get("coursePayload")):
        return None
    return {"places": d.get("places") or [], "coursePayload": d.get("coursePayload"), "route": d.get("route", ""),
            # 프론트 "내 코스에 담기" 카드용 — 어느 구장 지도에, 어떤 이동수단으로 그릴지
            "stadiumCode": d.get("stadiumCode"), "travel": d.get("travel")}


def checkpoint_receipt(turn, prefix, complete=False):
    return signing.dumps(
        {
            "turn": str(turn.pk),
            "user": turn.session.user_id,
            "session": turn.session_id,
            "length": len(prefix),
            "digest": hashlib.sha256(prefix.encode()).hexdigest(),
            "complete": complete,
        },
        key=settings.CHAT_CHECKPOINT_SIGNING_KEY,
        salt=RECEIPT_SALT,
        compress=True,
    )


@extend_schema_view(
    get=extend_schema(responses=ChatSessionSerializer(many=True)),
    post=extend_schema(request=ChatSessionSerializer, responses={201: ChatSessionSerializer}),
)
class ChatRoomView(generics.ListCreateAPIView):
    serializer_class = ChatSessionSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).order_by("-updated_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema_view(
    patch=extend_schema(request=ChatSessionSerializer, responses=ChatSessionSerializer),
    delete=extend_schema(responses={204: None}),
)
class ChatRoomDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ChatSessionSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ("patch", "delete", "options")
    lookup_url_kwarg = "session_id"

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)


@extend_schema_view(
    get=extend_schema(responses=ChatMessageSerializer(many=True)),
    post=extend_schema(
        request=ChatMessageSerializer,
        responses={
            (201, "application/json"): ChatNonStreamResponseSerializer,
            (200, "text/event-stream"): OpenApiResponse(
                PolymorphicProxySerializer(
                    component_name="MemberChatEventPayload",
                    serializers=(
                        ChatCheckpointEventSerializer,
                        ChatDeltaEventSerializer,
                        ChatDoneEventSerializer,
                        ChatErrorEventSerializer,
                    ),
                    resource_type_field_name=None,
                ),
                description="SSE checkpoint, delta, done, or error event payload",
            ),
        },
    ),
)
class ChatMessageView(generics.ListCreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = (IsAuthenticated,)
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, EventStreamRenderer)

    def get_queryset(self):
        return self.get_session().messages.order_by("sequence_no")

    def get_session(self):
        return generics.get_object_or_404(
            ChatSession, id=self.kwargs["session_id"], user=self.request.user
        )

    def create(self, request, *args, **kwargs):
        session = self.get_session()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["message"]
        if request.accepted_renderer.format == "sse":
            if not settings.CHAT_CHECKPOINT_SIGNING_KEY:
                return Response(
                    {"detail": "채팅 서명 설정이 필요합니다."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            turn = self.create_turn(session.pk, request.user.pk, question)
            return self.stream_response(request.user.pk, session.pk, turn)
        try:
            answer, saved = ChatService().invoke_with_messages(
                request.user.pk, session.pk, question
            )
        except OpenAIError:
            return Response(
                {"detail": "LLM 응답 생성에 실패했습니다. 다시 시도해 주세요."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        human, assistant = saved
        return Response(
            {
                "session_id": session.pk,
                "user_message": question,
                "assistant_message": answer,
                "status": "completed",
                "user_message_id": human.pk,
                "assistant_message_id": assistant.pk,
                **(course_meta() or {}),
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    @transaction.atomic
    def create_turn(session_id, user_id, question):
        session = ChatSession.objects.select_for_update().get(pk=session_id, user_id=user_id)
        base_sequence = session.messages.aggregate(last=Max("sequence_no"))["last"] or 0
        return ChatTurn.objects.create(
            session=session, question=question, base_sequence=base_sequence
        )

    @staticmethod
    def stream_response(user_id, session_id, turn):
        def events():
            stream, answer = None, ""
            try:
                yield sse(
                    "checkpoint",
                    {"turn_id": str(turn.pk), "receipt": checkpoint_receipt(turn, "")},
                )
                stream = ChatService().stream(user_id, session_id, turn.question)
                for chunk in stream:
                    answer += chunk
                    yield sse(
                        "delta",
                        {
                            "text": chunk,
                            "turn_id": str(turn.pk),
                            "receipt": checkpoint_receipt(turn, answer),
                        },
                    )
                if not answer.strip():
                    raise ValueError("Empty LLM response")
                yield sse(
                    "done",
                    {
                        "turn_id": str(turn.pk),
                        "receipt": checkpoint_receipt(turn, answer, complete=True),
                        # 코스 추천일 때만 붙는다. 프론트 파서는 done 의 모르는 키를 무시하므로
                        # 화면 수정 전에도 안 깨지고, 지도 카드·코스 저장 버튼이 붙을 때 읽어 쓰면 된다.
                        **(course_meta() or {}),
                    },
                )
            except GeneratorExit:
                raise
            except Exception:
                yield sse("error", {"detail": "답변 생성에 실패했습니다. 다시 시도해 주세요."})
            finally:
                close = getattr(stream, "close", None)
                if close:
                    with suppress(Exception):
                        close()

        response = StreamingHttpResponse(events(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response


class ChatFinalizeView(generics.GenericAPIView):
    serializer_class = ChatFinalizeSerializer
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=ChatFinalizeSerializer, responses=ChatFinalizeResponseSerializer)
    def post(self, request, turn_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        turn = generics.get_object_or_404(
            ChatTurn.objects.select_related("session"), pk=turn_id, session__user=request.user
        )
        try:
            receipt = signing.loads(
                data["receipt"],
                key=settings.CHAT_CHECKPOINT_SIGNING_KEY,
                salt=RECEIPT_SALT,
                max_age=RECEIPT_MAX_AGE,
            )
        except signing.BadSignature:
            raise serializers.ValidationError({"receipt": "유효하지 않은 체크포인트입니다."})
        prefix = data["prefix"]
        expected = {
            "turn": str(turn.pk),
            "user": request.user.pk,
            "session": turn.session_id,
            "length": len(prefix),
            "digest": hashlib.sha256(prefix.encode()).hexdigest(),
        }
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise serializers.ValidationError({"receipt": "체크포인트와 답변이 일치하지 않습니다."})
        if data["status"] == "completed" and (not receipt.get("complete") or not prefix.strip()):
            raise serializers.ValidationError({"status": "완료 체크포인트가 필요합니다."})
        return Response(self.finalize(turn.pk, data["status"], prefix))

    @staticmethod
    @transaction.atomic
    def finalize(turn_id, requested_status, prefix):
        turn = ChatTurn.objects.get(pk=turn_id)
        session = ChatSession.objects.select_for_update().get(pk=turn.session_id)
        turn = ChatTurn.objects.select_for_update().get(pk=turn_id)
        if turn.status == "stopped" or turn.status == requested_status:
            return ChatFinalizeView.result(turn)
        if turn.status == "completed":
            assistant = turn.assistant_message
            if not assistant or session.messages.filter(
                sequence_no__gt=assistant.sequence_no
            ).exists() or session.turns.exclude(pk=turn.pk).filter(
                base_sequence__gte=assistant.sequence_no
            ).exists():
                return ChatFinalizeView.result(turn)
            if prefix.strip():
                assistant.message = prefix
                assistant.status = "stopped"
                assistant.save(update_fields=("message", "status", "updated_at"))
            else:
                assistant.delete()
                turn.assistant_message = None
            turn.status = "stopped"
            turn.save(update_fields=("status", "assistant_message", "updated_at"))
            return ChatFinalizeView.result(turn)

        current_sequence = session.messages.aggregate(last=Max("sequence_no"))["last"] or 0
        if current_sequence != turn.base_sequence:
            raise Conflict()

        history = DjangoChatMessageHistory(
            user_id=session.user_id, session_id=session.pk
        )
        messages = [HumanMessage(content=turn.question)]
        if prefix.strip():
            messages.append(AIMessage(content=prefix))
        saved = history.add_messages(messages, assistant_status=requested_status)
        turn.human_message = saved[0]
        turn.assistant_message = saved[1] if len(saved) == 2 else None
        turn.status = requested_status
        turn.save(update_fields=("human_message", "assistant_message", "status", "updated_at"))
        session.save(update_fields=("updated_at",))
        return ChatFinalizeView.result(turn)

    @staticmethod
    def result(turn):
        return {
            "turn_id": str(turn.pk),
            "session_id": turn.session_id,
            "status": turn.status,
            "user_message_id": turn.human_message_id,
            "assistant_message_id": turn.assistant_message_id,
            "user_message": turn.question,
            "assistant_message": turn.assistant_message.message if turn.assistant_message else "",
        }


def guest_client_ip(request):
    raw = (
        request.META.get("HTTP_X_REAL_IP")
        if settings.CHAT_TRUST_PROXY_HEADERS
        else request.META.get("REMOTE_ADDR")
    ) or "unknown"
    try:
        return ipaddress.ip_address(raw).compressed
    except ValueError:
        return "unknown"


def guest_rate_limited(request):
    key = "chat-guest:" + hashlib.sha256(guest_client_ip(request).encode()).hexdigest()
    if cache.add(key, 1, timeout=settings.CHAT_GUEST_RATE_WINDOW):
        return False
    try:
        return cache.incr(key) > settings.CHAT_GUEST_RATE_LIMIT
    except ValueError:
        cache.set(key, 1, timeout=settings.CHAT_GUEST_RATE_WINDOW)
        return False


class GuestChatView(generics.GenericAPIView):
    serializer_class = GuestChatSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    renderer_classes = (JSONRenderer, EventStreamRenderer)

    @extend_schema(
        request=GuestChatSerializer,
        responses={
            (200, "text/event-stream"): OpenApiResponse(
                PolymorphicProxySerializer(
                    component_name="GuestChatEventPayload",
                    serializers=(
                        GuestChatDeltaEventSerializer,
                        GuestChatDoneEventSerializer,
                        ChatErrorEventSerializer,
                    ),
                    resource_type_field_name=None,
                ),
                description="SSE delta, done, or error event payload",
            )
        },
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if guest_rate_limited(request):
            return Response(
                {"detail": "요청이 많습니다. 잠시 후 다시 시도해 주세요."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        messages = serializer.validated_data["messages"]
        question = messages[-1]["content"]
        history = [
            (HumanMessage if item["role"] == "user" else AIMessage)(content=item["content"])
            for item in messages[:-1]
        ]

        def events():
            stream, answer = None, ""
            try:
                stream = ChatService().stream_with_history(history, question)
                for chunk in stream:
                    answer += chunk
                    yield sse("delta", {"text": chunk})
                if not answer.strip():
                    raise ValueError("Empty LLM response")
                yield sse("done", {"assistant_message": answer, **(course_meta() or {})})
            except GeneratorExit:
                raise
            except Exception:
                yield sse("error", {"detail": "답변 생성에 실패했습니다. 다시 시도해 주세요."})
            finally:
                close = getattr(stream, "close", None)
                if close:
                    with suppress(Exception):
                        close()

        response = StreamingHttpResponse(events(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response
