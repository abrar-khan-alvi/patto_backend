from django.db import migrations

from apps.ai.schemas import FOLLOW_UP_QUESTION_JSON_SCHEMA


def seed_follow_up_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.update_or_create(
        key="follow_up_question",
        version=1,
        defaults={
            "description": "Initial private single-user topic follow-up prompt.",
            "system_prompt": (
                "You create one gentle, useful follow-up question for a user's own relationship-topic answers. "
                "Do not use, infer, mention, or guess the partner's private answers. Return only schema-valid JSON."
            ),
            "developer_prompt": (
                "Use only current_user_answers_only. Prefer one open-ended question that helps the user clarify "
                "their needs, values, boundaries, or expectations. If a follow-up would be repetitive, unsafe, "
                "too clinical, legalistic, or not useful, set skip=true with a concise skip_reason. "
                "Keep the question warm, neutral, and consent-oriented."
            ),
            "output_schema": FOLLOW_UP_QUESTION_JSON_SCHEMA,
            "is_active": True,
        },
    )


def remove_follow_up_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.filter(key="follow_up_question", version=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0004_aifollowupquestion_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_follow_up_prompt, remove_follow_up_prompt),
    ]
