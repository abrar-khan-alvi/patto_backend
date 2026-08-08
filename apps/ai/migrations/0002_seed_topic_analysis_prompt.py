from django.db import migrations

from apps.ai.schemas import TOPIC_ANALYSIS_JSON_SCHEMA


def seed_topic_analysis_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.update_or_create(
        key="topic_analysis",
        version=1,
        defaults={
            "description": "Initial private couple topic analysis prompt.",
            "system_prompt": (
                "You analyze private relationship-topic responses for a couple. "
                "Be warm, balanced, non-judgmental, and practical. Do not diagnose. "
                "Do not reveal hidden chain-of-thought. Return only schema-valid JSON."
            ),
            "developer_prompt": (
                "Compare both partners' answers for the same frozen topic version. "
                "Highlight alignment, differences, strengths, growth areas, conversation starters, "
                "and suggested pact items. Keep suggestions respectful and consent-oriented. "
                "If content suggests immediate danger, add a safety note instead of escalating beyond the schema."
            ),
            "output_schema": TOPIC_ANALYSIS_JSON_SCHEMA,
            "is_active": True,
        },
    )


def remove_topic_analysis_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.filter(key="topic_analysis", version=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_topic_analysis_prompt, remove_topic_analysis_prompt),
    ]
