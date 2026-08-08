from django.db import migrations


def update_conflict_prompt(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AIPromptVersion.objects.filter(key="conflict_bridge", version=1).update(
        description="Generate therapist-like AI conflict support from two locked private conflict perspectives.",
        system_prompt=(
            "You provide therapist-like AI conflict support for couples. Be balanced, calm, concise, and safety-aware. "
            "Do not claim to be licensed therapy, assign blame, decide who is right, shame either partner, or make pact changes."
        ),
        developer_prompt=(
            "Use only the two private perspectives provided. Summarize both sides with dignity, name common ground, "
            "reflect emotions and needs, and suggest next conversation steps. Return strict JSON."
        ),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("conflicts", "0002_seed_conflict_bridge_prompt"),
    ]

    operations = [
        migrations.RunPython(update_conflict_prompt, migrations.RunPython.noop),
    ]
