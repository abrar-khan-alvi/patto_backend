import pytest
from django.test import override_settings

from apps.topics.models import Question, QuestionTranslation, Topic, TopicTranslation
from tests.helpers import authenticated_client


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_topic_list_returns_twelve_builtin_topics_with_question_counts():
    client = authenticated_client("person@example.com")

    response = client.get("/api/v1/topics/")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 12
    assert body[0]["slug"] == "fidelity"
    assert {topic["question_count"] for topic in body} == {12}


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_topic_detail_returns_versioned_questions_and_options():
    client = authenticated_client("person@example.com")

    response = client.get("/api/v1/topics/children-family-planning/")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Children & Family Planning"
    assert len(body["questions"]) == 12
    question_four = body["questions"][3]
    assert question_four["version"] == 1
    assert "biological children" in question_four["prompt"]
    assert len(question_four["options"]) == 4


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_catalog_uses_user_language_with_english_fallback():
    topic = Topic.objects.get(slug="money")
    TopicTranslation.objects.create(topic=topic, language="bn", title="Money BN", description="Bangla description")
    question = topic.questions.first()
    QuestionTranslation.objects.create(
        question=question,
        language="bn",
        prompt="Bangla prompt",
        open_text_prompt="Bangla open prompt",
    )
    client = authenticated_client("person@example.com")
    client.patch(
        "/api/v1/me/",
        {"preferred_language": "bn"},
        content_type="application/json",
    )

    response = client.get("/api/v1/topics/money/")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Money BN"
    assert body["questions"][0]["prompt"] == "Bangla prompt"
    assert body["questions"][0]["options"][0]["text"] == "This feels very important to me."


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_inactive_question_does_not_count_but_historical_row_remains():
    topic = Topic.objects.get(slug="health")
    question = topic.questions.order_by("sort_order").first()
    question.is_active = False
    question.save(update_fields=["is_active", "updated_at"])
    client = authenticated_client("person@example.com")

    response = client.get("/api/v1/topics/")

    assert response.status_code == 200
    health = next(item for item in response.json() if item["slug"] == "health")
    assert health["question_count"] == 11
    assert Question.objects.filter(id=question.id).exists()
