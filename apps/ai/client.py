import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.ai.exceptions import AIConfigurationError, AIProviderError


@dataclass(frozen=True)
class AIClientResponse:
    content: dict[str, Any] | None
    provider_response_id: str = ""
    usage: dict[str, Any] | None = None
    refusal_reason: str = ""


class OpenAIResponsesClient:
    def __init__(self, *, api_key: str | None = None, timeout_seconds: int | None = None):
        resolved_api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        if not resolved_api_key:
            raise AIConfigurationError("OPENAI_API_KEY is not configured.")
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise AIConfigurationError("The OpenAI Python SDK is not installed.") from exc
        self.client = OpenAI(
            api_key=resolved_api_key,
            timeout=timeout_seconds or settings.OPENAI_TIMEOUT_SECONDS,
            max_retries=settings.OPENAI_MAX_RETRIES,
        )

    def create_topic_analysis(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
    ) -> AIClientResponse:
        try:
            response = self.client.responses.create(
                model=model,
                input=input_messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "topic_analysis",
                        "schema": json_schema,
                        "strict": True,
                    }
                },
                store=settings.OPENAI_STORE_RESPONSES,
            )
        except Exception as exc:
            raise AIProviderError("OpenAI Responses API request failed.") from exc

        output_text = getattr(response, "output_text", "") or ""
        refusal_reason = extract_refusal_reason(response)
        if refusal_reason:
            return AIClientResponse(
                content=None,
                provider_response_id=getattr(response, "id", ""),
                usage=extract_usage(response),
                refusal_reason=refusal_reason,
            )
        try:
            content = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise AIProviderError("OpenAI response was not valid JSON.") from exc
        return AIClientResponse(
            content=content,
            provider_response_id=getattr(response, "id", ""),
            usage=extract_usage(response),
        )

    def create_follow_up_question(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
    ) -> AIClientResponse:
        return self.create_structured_response(
            model=model,
            input_messages=input_messages,
            json_schema=json_schema,
            schema_name="follow_up_question",
        )

    def create_structured_response(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
        schema_name: str,
    ) -> AIClientResponse:
        try:
            response = self.client.responses.create(
                model=model,
                input=input_messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": json_schema,
                        "strict": True,
                    }
                },
                store=settings.OPENAI_STORE_RESPONSES,
            )
        except Exception as exc:
            raise AIProviderError("OpenAI Responses API request failed.") from exc

        output_text = getattr(response, "output_text", "") or ""
        refusal_reason = extract_refusal_reason(response)
        if refusal_reason:
            return AIClientResponse(
                content=None,
                provider_response_id=getattr(response, "id", ""),
                usage=extract_usage(response),
                refusal_reason=refusal_reason,
            )
        try:
            content = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise AIProviderError("OpenAI response was not valid JSON.") from exc
        return AIClientResponse(
            content=content,
            provider_response_id=getattr(response, "id", ""),
            usage=extract_usage(response),
        )


def extract_usage(response) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {}


def extract_refusal_reason(response) -> str:
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            refusal = getattr(content_item, "refusal", "")
            if refusal:
                return str(refusal)
    return ""
