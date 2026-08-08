from pydantic import BaseModel, ConfigDict, Field


class MonthlyInsightSectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1200)
    highlights: list[str] = Field(default_factory=list, max_length=6)


class MonthlyInsightSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month_summary: str = Field(min_length=1, max_length=1200)
    connection_patterns: list[str] = Field(min_length=1, max_length=6)
    growth_opportunities: list[str] = Field(min_length=1, max_length=6)
    suggested_rituals: list[str] = Field(default_factory=list, max_length=6)
    sections: list[MonthlyInsightSectionSchema] = Field(min_length=1, max_length=8)
    safety_flags: list[str] = Field(default_factory=list, max_length=8)


MONTHLY_INSIGHT_JSON_SCHEMA = MonthlyInsightSchema.model_json_schema()
