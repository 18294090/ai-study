from openai import OpenAI
from anthropic import Anthropic
from pydantic import BaseModel
from typing import Type, TypeVar

T = TypeVar("T", bound=BaseModel)


class StructuredClient:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    def extract(
        self,
        system: str,
        user: str,
        schema: Type[T],
        cached_prefix: str | None = None,
    ) -> T:
        messages = []
        if cached_prefix:
            messages.append({"role": "system", "content": cached_prefix})
        messages += [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        resp = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=schema,
        )
        return resp.choices[0].message.parsed


class AnthropicStructuredClient:
    def __init__(self, client: Anthropic, model: str):
        self.client = client
        self.model = model

    def extract(
        self,
        system: str,
        user: str,
        schema: Type[T],
        cached_prefix: str | None = None,
    ) -> T:
        messages = []
        if cached_prefix:
            messages.append(
                {"role": "user", "content": [{"type": "text", "text": cached_prefix, "cache_control": {"type": "ephemeral"}}]}
            )
        messages += [
            {"role": "user", "content": system},
            {"role": "user", "content": user},
        ]
        resp = self.client.messages.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json", "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}},
        )
        import json
        return schema.model_validate_json(resp.content[0].text)