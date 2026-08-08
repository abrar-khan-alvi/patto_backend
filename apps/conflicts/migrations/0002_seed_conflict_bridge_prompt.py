from django.db import migrations


CONFLICT_BRIDGE_SCHEMA = {
    "properties": {
        "neutral_summary": {"maxLength": 1600, "minLength": 1, "title": "Neutral Summary", "type": "string"},
        "partner_summaries": {"additionalProperties": {"type": "string"}, "title": "Partner Summaries", "type": "object"},
        "common_ground": {"items": {"type": "string"}, "maxItems": 6, "title": "Common Ground", "type": "array"},
        "next_steps": {"items": {"type": "string"}, "maxItems": 6, "title": "Next Steps", "type": "array"},
        "safety_flags": {"items": {"type": "string"}, "maxItems": 8, "title": "Safety Flags", "type": "array"},
    },
    "required": ["neutral_summary", "partner_summaries", "common_ground", "next_steps", "safety_flags"],
    "title": "ConflictBridgeSchema",
    "type": "object",
    "additionalProperties": False,
}


def seed_conflict_bridge_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.update_or_create(
        key="conflict_bridge",
        version=1,
        defaults={
            "description": "Generate therapist-like AI conflict support from two locked private conflict perspectives.",
            "system_prompt": (
                "You provide therapist-like AI conflict support for couples. Be balanced, calm, concise, and safety-aware. "
                "Do not claim to be licensed therapy, assign blame, decide who is right, shame either partner, or make pact changes."
            ),
            "developer_prompt": (
                "Use only the two private perspectives provided. Summarize both sides with dignity, name common ground, "
                "reflect emotions and needs, and suggest next conversation steps. Return strict JSON."
            ),
            "output_schema": CONFLICT_BRIDGE_SCHEMA,
            "is_active": True,
        },
    )


def remove_conflict_bridge_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.filter(key="conflict_bridge", version=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0005_seed_follow_up_prompt"),
        ("conflicts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_conflict_bridge_prompt, remove_conflict_bridge_prompt),
    ]
