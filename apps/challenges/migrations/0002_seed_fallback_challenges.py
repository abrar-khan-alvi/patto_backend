from django.db import migrations


CHALLENGES = [
    (
        "daily-appreciation-note",
        "Daily appreciation note",
        "Each partner shares one specific appreciation before the day ends.",
        "Use one sentence that starts with: I appreciated when you...",
        "appreciation",
        "fallback",
        1,
        10,
    ),
    (
        "ten-minute-check-in",
        "Ten-minute check-in",
        "Set a timer for ten minutes and ask each other what support would feel helpful this week.",
        "Listen without fixing first; then each person names one small action.",
        "communication",
        "fallback",
        1,
        20,
    ),
    (
        "shared-planning-pause",
        "Shared planning pause",
        "Pick one household or calendar item and plan it together kindly.",
        "Keep the scope tiny enough to finish in one conversation.",
        "teamwork",
        "fallback",
        1,
        30,
    ),
    (
        "gentle-repair-signal",
        "Gentle repair signal",
        "Agree on one kind phrase either partner can use when a conversation needs a reset.",
        "The phrase should invite a pause, not assign blame.",
        "repair",
        "curated",
        2,
        40,
    ),
    (
        "mini-quality-time",
        "Mini quality-time ritual",
        "Choose one simple activity to do together without phones for fifteen minutes.",
        "Tea, a short walk, or music together all count.",
        "quality_time",
        "curated",
        1,
        50,
    ),
]


def seed_challenges(apps, schema_editor):
    Challenge = apps.get_model("challenges", "Challenge")
    for stable_key, title, description, instructions, category, source, duration_days, sort_order in CHALLENGES:
        Challenge.objects.update_or_create(
            stable_key=stable_key,
            defaults={
                "title": title,
                "description": description,
                "instructions": instructions,
                "category": category,
                "source": source,
                "duration_days": duration_days,
                "sort_order": sort_order,
                "is_active": True,
                "safety_policy_version": "challenge_policy_v1",
            },
        )


def unseed_challenges(apps, schema_editor):
    Challenge = apps.get_model("challenges", "Challenge")
    Challenge.objects.filter(stable_key__in=[item[0] for item in CHALLENGES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("challenges", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_challenges, unseed_challenges),
    ]
