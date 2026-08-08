from django.db import migrations


def update_coach_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.filter(key="coach", version=1).update(
        description="Relationship Coach response for individual user-to-AI conversations.",
        system_prompt=(
            "You are Patto's individual relationship Coach. Be warm, practical, nonjudgmental, and concise. "
            "Do not diagnose, coerce, shame, or provide legal/medical advice."
        ),
        developer_prompt=(
            "This prompt is for individual user-to-AI Coach conversations only. Individual Coach content is private unless "
            "explicitly shared by the user. Offer small next steps and safety-aware guidance."
        ),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coach", "0002_seed_coach_prompt"),
    ]

    operations = [
        migrations.RunPython(update_coach_prompt, migrations.RunPython.noop),
    ]
