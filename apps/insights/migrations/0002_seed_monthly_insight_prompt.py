from django.db import migrations


MONTHLY_INSIGHT_SCHEMA = {
    "properties": {
        "month_summary": {"maxLength": 1200, "minLength": 1, "title": "Month Summary", "type": "string"},
        "connection_patterns": {
            "items": {"type": "string"},
            "maxItems": 6,
            "minItems": 1,
            "title": "Connection Patterns",
            "type": "array",
        },
        "growth_opportunities": {
            "items": {"type": "string"},
            "maxItems": 6,
            "minItems": 1,
            "title": "Growth Opportunities",
            "type": "array",
        },
        "suggested_rituals": {
            "items": {"type": "string"},
            "maxItems": 6,
            "title": "Suggested Rituals",
            "type": "array",
        },
        "sections": {
            "items": {
                "properties": {
                    "title": {"maxLength": 120, "minLength": 1, "title": "Title", "type": "string"},
                    "body": {"maxLength": 1200, "minLength": 1, "title": "Body", "type": "string"},
                    "highlights": {
                        "items": {"type": "string"},
                        "maxItems": 6,
                        "title": "Highlights",
                        "type": "array",
                    },
                },
                "required": ["title", "body", "highlights"],
                "title": "MonthlyInsightSectionSchema",
                "type": "object",
                "additionalProperties": False,
            },
            "maxItems": 8,
            "minItems": 1,
            "title": "Sections",
            "type": "array",
        },
        "safety_flags": {
            "items": {"type": "string"},
            "maxItems": 8,
            "title": "Safety Flags",
            "type": "array",
        },
    },
    "required": [
        "month_summary",
        "connection_patterns",
        "growth_opportunities",
        "suggested_rituals",
        "sections",
        "safety_flags",
    ],
    "title": "MonthlyInsightSchema",
    "type": "object",
    "additionalProperties": False,
}


def seed_monthly_insight_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.update_or_create(
        key="monthly_insight",
        version=1,
        defaults={
            "description": "Summarize a couple's revealed daily-question answers for a closed month.",
            "system_prompt": (
                "You create warm, grounded monthly relationship insights for couples. "
                "Use only the provided revealed daily answers. Do not diagnose, shame, or make unsafe recommendations."
            ),
            "developer_prompt": (
                "Return concise structured JSON. Focus on patterns, appreciation, communication opportunities, "
                "and small practical rituals. If safety concerns appear, include them only in safety_flags."
            ),
            "output_schema": MONTHLY_INSIGHT_SCHEMA,
            "is_active": True,
        },
    )


def remove_monthly_insight_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.filter(key="monthly_insight", version=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0005_seed_follow_up_prompt"),
        ("insights", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_monthly_insight_prompt, remove_monthly_insight_prompt),
    ]
