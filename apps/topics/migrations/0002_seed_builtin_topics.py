from django.db import migrations


TOPICS = [
    ("fidelity", "Fidelity", "heart", "Trust, boundaries, commitment, and exclusivity."),
    ("money", "Money", "money", "Spending, saving, debt, income, and financial priorities."),
    ("children-family-planning", "Children & Family Planning", "children", "Children, timing, fertility, adoption, and parenting expectations."),
    ("home", "Home", "home", "Living space, chores, routines, hospitality, and daily logistics."),
    ("future", "Future", "future", "Long-term plans, location, ambition, retirement, and shared direction."),
    ("conflict", "Conflict", "conflict", "Arguments, repair, accountability, escalation, and emotional safety."),
    ("separation", "Separation", "separation", "Breakup rules, space, assets, pets, privacy, and what happens if things end."),
    ("family-in-laws", "Family & In-laws", "family", "Parents, siblings, boundaries, holidays, caregiving, and family expectations."),
    ("intimacy", "Intimacy", "intimacy", "Affection, sex, desire, closeness, rejection, and emotional connection."),
    ("career", "Career", "career", "Work, ambition, money pressure, schedules, relocation, and support."),
    ("friends", "Friends", "friends", "Social life, alone time, friend boundaries, exes, and community."),
    ("health", "Health", "health", "Physical health, mental wellbeing, habits, care, and lifestyle."),
]

QUESTION_TEMPLATES = [
    "What does a healthy agreement about {topic_lower} look like to you?",
    "Where do you feel most flexible about {topic_lower}?",
    "Where do you feel least willing to compromise about {topic_lower}?",
    "What would you want your partner to understand before making decisions about {topic_lower}?",
    "What past experience shapes how you think about {topic_lower}?",
    "What would make you feel respected in this area?",
    "What would make you feel unsafe, dismissed, or unsupported in this area?",
    "How should you and your partner handle a disagreement about {topic_lower}?",
    "What should happen if one of you changes your mind later?",
    "What practical rule would help both of you in this area?",
    "What is one fear you have about {topic_lower}?",
    "What is one hope you have about {topic_lower}?",
]

CHILDREN_Q4 = "If one of you discovered you could not have biological children, what would you want to explore?"

DEFAULT_OPTIONS = [
    ("strong_yes", "This feels very important to me."),
    ("open", "I am open, but I would want a deeper conversation."),
    ("unsure", "I am not sure yet."),
    ("not_aligned", "I may feel differently from my partner here."),
]

CHILDREN_Q4_OPTIONS = [
    ("adoption", "Adoption. I feel as open to it as having biological children."),
    ("medical_options", "Medical options first, such as IVF or other treatments."),
    ("all_options", "We would explore all available options together."),
    ("need_time", "I would need time to process. I honestly do not know yet."),
]


def seed_builtin_topics(apps, schema_editor):
    Topic = apps.get_model("topics", "Topic")
    TopicTranslation = apps.get_model("topics", "TopicTranslation")
    Question = apps.get_model("topics", "Question")
    QuestionTranslation = apps.get_model("topics", "QuestionTranslation")
    QuestionOption = apps.get_model("topics", "QuestionOption")
    QuestionOptionTranslation = apps.get_model("topics", "QuestionOptionTranslation")

    for topic_index, (slug, title, icon, description) in enumerate(TOPICS, start=1):
        topic, _ = Topic.objects.update_or_create(
            stable_key=slug,
            defaults={
                "slug": slug,
                "icon": icon,
                "sort_order": topic_index,
                "version": 1,
                "is_active": True,
            },
        )
        TopicTranslation.objects.update_or_create(
            topic=topic,
            language="en",
            defaults={"title": title, "description": description},
        )

        for question_index, template in enumerate(QUESTION_TEMPLATES, start=1):
            stable_key = f"{slug}-q{question_index:02d}"
            prompt = template.format(topic_lower=title.lower())
            options = DEFAULT_OPTIONS
            if slug == "children-family-planning" and question_index == 4:
                prompt = CHILDREN_Q4
                options = CHILDREN_Q4_OPTIONS

            question, _ = Question.objects.update_or_create(
                topic=topic,
                stable_key=stable_key,
                version=1,
                defaults={
                    "kind": "single_choice_with_text",
                    "sort_order": question_index,
                    "is_active": True,
                },
            )
            QuestionTranslation.objects.update_or_create(
                question=question,
                language="en",
                defaults={
                    "prompt": prompt,
                    "open_text_prompt": "Why did you choose this? What matters most to you here?",
                },
            )
            for option_index, (option_key, option_text) in enumerate(options, start=1):
                option, _ = QuestionOption.objects.update_or_create(
                    question=question,
                    stable_key=option_key,
                    defaults={"sort_order": option_index},
                )
                QuestionOptionTranslation.objects.update_or_create(
                    option=option,
                    language="en",
                    defaults={"text": option_text},
                )


def remove_builtin_topics(apps, schema_editor):
    Topic = apps.get_model("topics", "Topic")
    Question = apps.get_model("topics", "Question")
    topics = Topic.objects.filter(stable_key__in=[topic[0] for topic in TOPICS])
    Question.objects.filter(topic__in=topics).delete()
    topics.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("topics", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_builtin_topics, remove_builtin_topics),
    ]
