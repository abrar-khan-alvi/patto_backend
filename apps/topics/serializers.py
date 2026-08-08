from rest_framework import serializers

from apps.topics.models import CoupleTopic, CustomQuestion, CustomQuestionOption, Question, QuestionOption, Topic


def preferred_language(context) -> str:
    request = context.get("request")
    if request and getattr(request, "user", None) and request.user.is_authenticated:
        return getattr(request.user, "preferred_language", "en") or "en"
    return "en"


def translation_for(instance, language: str):
    translations = list(getattr(instance, "translations").all())
    for translation in translations:
        if translation.language == language:
            return translation
    for translation in translations:
        if translation.language == "en":
            return translation
    return translations[0] if translations else None


class QuestionOptionSerializer(serializers.ModelSerializer):
    text = serializers.SerializerMethodField()

    class Meta:
        model = QuestionOption
        fields = ["id", "stable_key", "sort_order", "text"]

    def get_text(self, obj):
        translation = translation_for(obj, preferred_language(self.context))
        return translation.text if translation else ""


class QuestionSerializer(serializers.ModelSerializer):
    prompt = serializers.SerializerMethodField()
    open_text_prompt = serializers.SerializerMethodField()
    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "stable_key",
            "kind",
            "sort_order",
            "version",
            "is_active",
            "prompt",
            "open_text_prompt",
            "options",
        ]

    def get_prompt(self, obj):
        translation = translation_for(obj, preferred_language(self.context))
        return translation.prompt if translation else ""

    def get_open_text_prompt(self, obj):
        translation = translation_for(obj, preferred_language(self.context))
        return translation.open_text_prompt if translation else ""


class TopicListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = [
            "id",
            "slug",
            "stable_key",
            "icon",
            "sort_order",
            "version",
            "is_active",
            "title",
            "description",
            "question_count",
        ]

    def get_title(self, obj):
        translation = translation_for(obj, preferred_language(self.context))
        return translation.title if translation else obj.slug

    def get_description(self, obj):
        translation = translation_for(obj, preferred_language(self.context))
        return translation.description if translation else ""

    def get_question_count(self, obj):
        return getattr(obj, "active_question_count", None) or obj.questions.filter(is_active=True).count()


class TopicDetailSerializer(TopicListSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta(TopicListSerializer.Meta):
        fields = TopicListSerializer.Meta.fields + ["questions"]


class CustomQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomQuestionOption
        fields = ["id", "stable_key", "sort_order", "text"]


class CustomQuestionSerializer(serializers.ModelSerializer):
    options = CustomQuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = CustomQuestion
        fields = [
            "id",
            "stable_key",
            "kind",
            "sort_order",
            "version",
            "is_active",
            "prompt",
            "open_text_prompt",
            "options",
        ]


class CoupleTopicSerializer(serializers.ModelSerializer):
    questions = CustomQuestionSerializer(many=True, read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = CoupleTopic
        fields = [
            "id",
            "stable_key",
            "icon",
            "title",
            "description",
            "version",
            "is_active",
            "is_locked",
            "supersedes",
            "created_at",
            "question_count",
            "questions",
        ]

    def get_question_count(self, obj):
        return obj.questions.filter(is_active=True).count()


class CustomQuestionOptionWriteSerializer(serializers.Serializer):
    stable_key = serializers.CharField(required=False, max_length=160)
    text = serializers.CharField()


class CustomQuestionWriteSerializer(serializers.Serializer):
    stable_key = serializers.CharField(required=False, max_length=160)
    kind = serializers.ChoiceField(choices=CustomQuestion.Kind.choices, default=CustomQuestion.Kind.SINGLE_CHOICE_WITH_TEXT)
    prompt = serializers.CharField()
    open_text_prompt = serializers.CharField(required=False, allow_blank=True)
    options = CustomQuestionOptionWriteSerializer(many=True, required=False)


class CoupleTopicWriteSerializer(serializers.Serializer):
    icon = serializers.CharField(required=False, allow_blank=True, max_length=40)
    title = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False, allow_blank=True)
    questions = CustomQuestionWriteSerializer(many=True)
