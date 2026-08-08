from pydantic import BaseModel, ConfigDict, Field, model_validator


class TopicAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_summary: str = Field(min_length=1, max_length=1200)
    alignment_score: int = Field(ge=0, le=100)
    strengths: list[str] = Field(min_length=1, max_length=6)
    growth_areas: list[str] = Field(min_length=1, max_length=6)
    conversation_starters: list[str] = Field(min_length=1, max_length=8)
    suggested_pact_items: list[str] = Field(min_length=1, max_length=8)
    safety_notes: list[str] = Field(default_factory=list, max_length=6)


TOPIC_ANALYSIS_JSON_SCHEMA = TopicAnalysisSchema.model_json_schema()


class FollowUpQuestionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    follow_up_question: str = Field(default="", max_length=500)
    internal_reason: str = Field(min_length=1, max_length=1000)
    topic_stable_key: str = Field(min_length=1, max_length=160)
    topic_version: int = Field(ge=1)
    skip: bool = False
    skip_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def require_question_or_skip(self):
        if self.skip and not self.skip_reason:
            raise ValueError("skip_reason is required when skip is true.")
        if not self.skip and not self.follow_up_question:
            raise ValueError("follow_up_question is required when skip is false.")
        return self


FOLLOW_UP_QUESTION_JSON_SCHEMA = FollowUpQuestionSchema.model_json_schema()
