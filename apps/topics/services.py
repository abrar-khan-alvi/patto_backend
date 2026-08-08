import re
import uuid

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.common.services import record_audit_event
from apps.couples.models import Couple
from apps.couples.permissions import user_is_active_couple_member
from apps.topics.models import CoupleTopic, CustomQuestion, CustomQuestionOption


MIN_CUSTOM_QUESTIONS = 3


def slugify_key(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:80] or f"custom-{uuid.uuid4().hex[:12]}"


def ensure_can_manage_custom_topic(*, user: User, couple: Couple) -> None:
    if not user_is_active_couple_member(user, couple):
        raise PermissionDenied("Only active couple members can manage custom topics.")


def validate_questions(questions: list[dict]) -> None:
    if len(questions) < MIN_CUSTOM_QUESTIONS:
        raise ValidationError({"questions": f"Add at least {MIN_CUSTOM_QUESTIONS} questions."})
    for index, question in enumerate(questions, start=1):
        if not question.get("prompt"):
            raise ValidationError({"questions": f"Question {index} needs prompt text."})
        options = question.get("options") or []
        if question.get("kind", CustomQuestion.Kind.SINGLE_CHOICE_WITH_TEXT) == CustomQuestion.Kind.SINGLE_CHOICE_WITH_TEXT:
            if len(options) < 2:
                raise ValidationError({"questions": f"Question {index} needs at least 2 options."})


@transaction.atomic
def create_custom_topic(*, couple: Couple, created_by: User, data: dict, request_id: str = "") -> CoupleTopic:
    ensure_can_manage_custom_topic(user=created_by, couple=couple)
    questions = data.get("questions") or []
    validate_questions(questions)
    stable_key = slugify_key(data["title"])
    topic = CoupleTopic.objects.create(
        couple=couple,
        created_by=created_by,
        stable_key=stable_key,
        icon=data.get("icon", ""),
        title=data["title"],
        description=data.get("description", ""),
        version=1,
    )
    replace_custom_questions(topic=topic, questions=questions, version=1)
    record_audit_event(action="custom_topic.created", actor=created_by, target=topic, request_id=request_id)
    return topic


@transaction.atomic
def update_custom_topic(*, topic: CoupleTopic, updated_by: User, data: dict, request_id: str = "") -> CoupleTopic:
    ensure_can_manage_custom_topic(user=updated_by, couple=topic.couple)
    questions = data.get("questions") or []
    validate_questions(questions)
    if topic.is_locked:
        return clone_custom_topic_version(topic=topic, updated_by=updated_by, data=data, request_id=request_id)

    topic.icon = data.get("icon", topic.icon)
    topic.title = data["title"]
    topic.description = data.get("description", "")
    topic.save(update_fields=["icon", "title", "description", "updated_at"])
    topic.questions.all().delete()
    replace_custom_questions(topic=topic, questions=questions, version=topic.version)
    record_audit_event(action="custom_topic.updated", actor=updated_by, target=topic, request_id=request_id)
    return topic


@transaction.atomic
def clone_custom_topic_version(*, topic: CoupleTopic, updated_by: User, data: dict, request_id: str = "") -> CoupleTopic:
    topic.is_active = False
    topic.save(update_fields=["is_active", "updated_at"])
    new_topic = CoupleTopic.objects.create(
        couple=topic.couple,
        created_by=updated_by,
        stable_key=topic.stable_key,
        icon=data.get("icon", topic.icon),
        title=data["title"],
        description=data.get("description", ""),
        version=topic.version + 1,
        supersedes=topic,
    )
    replace_custom_questions(topic=new_topic, questions=data.get("questions") or [], version=new_topic.version)
    record_audit_event(action="custom_topic.version_created", actor=updated_by, target=new_topic, request_id=request_id)
    return new_topic


@transaction.atomic
def deactivate_custom_topic(*, topic: CoupleTopic, deleted_by: User, request_id: str = "") -> None:
    ensure_can_manage_custom_topic(user=deleted_by, couple=topic.couple)
    if topic.is_active:
        topic.is_active = False
        topic.save(update_fields=["is_active", "updated_at"])
        record_audit_event(action="custom_topic.deactivated", actor=deleted_by, target=topic, request_id=request_id)


def mark_custom_topic_locked(topic: CoupleTopic) -> None:
    if not topic.is_locked:
        topic.is_locked = True
        topic.save(update_fields=["is_locked", "updated_at"])


def replace_custom_questions(*, topic: CoupleTopic, questions: list[dict], version: int) -> None:
    for question_index, question_data in enumerate(questions, start=1):
        question = CustomQuestion.objects.create(
            topic=topic,
            stable_key=question_data.get("stable_key") or f"{topic.stable_key}-q{question_index:02d}",
            kind=question_data.get("kind", CustomQuestion.Kind.SINGLE_CHOICE_WITH_TEXT),
            prompt=question_data["prompt"],
            open_text_prompt=question_data.get("open_text_prompt", "Why did you choose this? What matters most to you here?"),
            sort_order=question_index,
            version=version,
        )
        for option_index, option_data in enumerate(question_data.get("options") or [], start=1):
            CustomQuestionOption.objects.create(
                question=question,
                stable_key=option_data.get("stable_key") or f"option-{option_index}",
                text=option_data["text"],
                sort_order=option_index,
            )
