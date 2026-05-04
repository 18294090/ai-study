from __future__ import annotations
from typing import Type
from pydantic import BaseModel
import os

from .types import Intent, IntentResult


SYSTEM_PROMPT = """你是一个意图分类专家。根据用户问题判断其意图类型：

- factual: 具体知识点查询，如"什么是X"、"X的定义"
- procedural: 步骤/过程类问题，如"如何做X"、"X的步骤"
- explanatory: 概念解释类，如"为什么X"、"X的原理"
- meta: 关于学习本身的问题，如"应该先学X还是Y"、"如何学习X"

输出JSON格式，包含intent（字符串）、confidence（0-1）、reasoning（简短理由）。"""


class IntentClassifier:
    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def classify(self, question: str) -> IntentResult:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            response_format={"type": "json_object"},
        )
        import json
        data = json.loads(response.choices[0].message.content)
        return IntentResult(
            intent=Intent(data["intent"]),
            confidence=float(data.get("confidence", 0.8)),
            reasoning=data.get("reasoning", ""),
        )

    def classify_sync(self, question: str) -> IntentResult:
        return self.classify(question)