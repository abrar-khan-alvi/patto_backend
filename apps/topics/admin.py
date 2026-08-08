from django.contrib import admin

from apps.topics.models import (
    CoupleTopic,
    CustomQuestion,
    CustomQuestionOption,
    Question,
    QuestionOption,
    QuestionOptionTranslation,
    QuestionTranslation,
    Topic,
    TopicTranslation,
)


class TopicTranslationInline(admin.TabularInline):
    model = TopicTranslation
    extra = 0


class QuestionTranslationInline(admin.TabularInline):
    model = QuestionTranslation
    extra = 0


class QuestionOptionTranslationInline(admin.TabularInline):
    model = QuestionOptionTranslation
    extra = 0


class CustomQuestionInline(admin.TabularInline):
    model = CustomQuestion
    extra = 0
    readonly_fields = ("created_at", "updated_at")


class CustomQuestionOptionInline(admin.TabularInline):
    model = CustomQuestionOption
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("slug", "stable_key", "sort_order", "version", "is_active")
    list_filter = ("is_active",)
    search_fields = ("slug", "stable_key", "translations__title")
    inlines = [TopicTranslationInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("topic", "stable_key", "sort_order", "version", "kind", "is_active")
    list_filter = ("topic", "kind", "is_active")
    search_fields = ("stable_key", "translations__prompt")
    inlines = [QuestionTranslationInline]


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ("question", "stable_key", "sort_order")
    search_fields = ("stable_key", "translations__text")
    inlines = [QuestionOptionTranslationInline]


@admin.register(CoupleTopic)
class CoupleTopicAdmin(admin.ModelAdmin):
    list_display = ("title", "couple", "created_by", "version", "is_active", "is_locked")
    list_filter = ("is_active", "is_locked")
    search_fields = ("title", "stable_key", "couple__id", "created_by__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [CustomQuestionInline]


@admin.register(CustomQuestion)
class CustomQuestionAdmin(admin.ModelAdmin):
    list_display = ("topic", "stable_key", "sort_order", "version", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("prompt", "stable_key", "topic__title")
    inlines = [CustomQuestionOptionInline]
