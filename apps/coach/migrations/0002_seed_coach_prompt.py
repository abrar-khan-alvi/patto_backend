from django.db import migrations


COACH_RESPONSE_SCHEMA = {
    "properties": {
        "message": {"maxLength": 2000, "minLength": 1, "title": "Message", "type": "string"},
        "suggested_next_steps": {
            "items": {"type": "string"},
            "maxItems": 5,
            "title": "Suggested Next Steps",
            "type": "array",
        },
        "safety_flags": {
            "items": {"type": "string"},
            "maxItems": 8,
            "title": "Safety Flags",
            "type": "array",
        },
    },
    "required": ["message", "suggested_next_steps", "safety_flags"],
    "title": "CoachResponseSchema",
    "type": "object",
    "additionalProperties": False,
}


def seed_coach_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.update_or_create(
        key="coach",
        version=1,
        defaults={
            "description": "Relationship Coach response for individual user-to-AI conversations.",
            "system_prompt": (
                "You are Patto's individual relationship Coach. Be warm, practical, nonjudgmental, and concise. "
                "Do not diagnose, coerce, shame, or provide legal/medical advice."
            ),
            "developer_prompt": (
                "This prompt is for individual user-to-AI Coach conversations only. Individual Coach content is private unless "
                "explicitly shared by the user. Offer small next steps and safety-aware guidance."
            ),
            "output_schema": COACH_RESPONSE_SCHEMA,
            "is_active": True,
        },
    )


def remove_coach_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.filter(key="coach", version=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0005_seed_follow_up_prompt"),
        ("coach", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_coach_prompt, remove_coach_prompt),
    ]
