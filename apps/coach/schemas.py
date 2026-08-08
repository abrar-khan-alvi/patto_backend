from pydantic import BaseModel, ConfigDict, Field


class CoachResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    suggested_next_steps: list[str] = Field(default_factory=list, max_length=5)
    safety_flags: list[str] = Field(default_factory=list, max_length=8)


COACH_RESPONSE_JSON_SCHEMA = CoachResponseSchema.model_json_schema()
