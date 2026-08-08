from django.db import migrations


DAILY_QUESTIONS = [
    (
        "small-support-today",
        "How could your partner support you in one small way today?",
        "support",
        10,
    ),
    (
        "moment-appreciated",
        "What is one thing your partner did recently that you appreciated?",
        "appreciation",
        20,
    ),
    (
        "energy-check",
        "What is your emotional energy level today, and what would help it?",
        "check_in",
        30,
    ),
    (
        "shared-laugh",
        "What is a tiny moment from your relationship that still makes you smile?",
        "connection",
        40,
    ),
    (
        "stress-signal",
        "When you are stressed today, what sign should your partner look for?",
        "communication",
        50,
    ),
    (
        "quality-time",
        "What would make ten minutes together feel meaningful today?",
        "quality_time",
        60,
    ),
    (
        "repair-gesture",
        "If something feels tense today, what repair gesture would feel good to you?",
        "repair",
        70,
    ),
]


def seed_daily_questions(apps, schema_editor):
    DailyQuestion = apps.get_model("daily", "DailyQuestion")
    for stable_key, prompt, category, sort_order in DAILY_QUESTIONS:
        DailyQuestion.objects.update_or_create(
            stable_key=stable_key,
            defaults={
                "prompt": prompt,
                "category": category,
                "sort_order": sort_order,
                "is_active": True,
            },
        )


def unseed_daily_questions(apps, schema_editor):
    DailyQuestion = apps.get_model("daily", "DailyQuestion")
    DailyQuestion.objects.filter(stable_key__in=[item[0] for item in DAILY_QUESTIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("daily", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_daily_questions, unseed_daily_questions),
    ]
