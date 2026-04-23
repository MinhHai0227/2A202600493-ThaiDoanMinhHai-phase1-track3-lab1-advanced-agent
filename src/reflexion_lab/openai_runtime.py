from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError

from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import JudgeResult, QAExample, ReflectionEntry


@dataclass
class LLMResult:
    content: str
    tokens: int
    latency_ms: int


def _context_text(example: QAExample) -> str:
    return "\n\n".join(f"[{chunk.title}]\n{chunk.text}" for chunk in example.context)


def _usage_tokens(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    total = getattr(usage, "total_tokens", None)
    if total is not None:
        return int(total)
    input_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", 0) or 0
    return int(input_tokens + output_tokens)


class OpenAIRuntime:
    def __init__(self, model: str | None = None) -> None:
        load_dotenv()
        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _chat(self, system: str, user: str, *, json_mode: bool = False) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        response = self.client.chat.completions.create(**kwargs)
        latency_ms = round((time.perf_counter() - started) * 1000)
        content = response.choices[0].message.content or ""
        return LLMResult(content=content.strip(), tokens=_usage_tokens(response), latency_ms=latency_ms)

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> LLMResult:
        reflections = "\n".join(f"- {item}" for item in reflection_memory) or "None"
        user = f"""Question:
{example.question}

Context:
{_context_text(example)}

Agent type: {agent_type}
Attempt: {attempt_id}
Reflection memory:
{reflections}

Return only the final short answer."""
        return self._chat(ACTOR_SYSTEM, user)

    def evaluator(self, example: QAExample, answer: str) -> tuple[JudgeResult, LLMResult]:
        user = f"""Gold answer: {example.gold_answer}
Predicted answer: {answer}

Question:
{example.question}

Context:
{_context_text(example)}

Return JSON only."""
        result = self._chat(EVALUATOR_SYSTEM, user, json_mode=True)
        try:
            judge = JudgeResult.model_validate_json(result.content)
        except (ValidationError, json.JSONDecodeError):
            judge = JudgeResult(
                score=0,
                reason=f"Evaluator returned invalid JSON: {result.content[:200]}",
                missing_evidence=[],
                spurious_claims=[answer],
            )
        return judge, result

    def reflector(self, example: QAExample, attempt_id: int, judge: JudgeResult, answer: str) -> tuple[ReflectionEntry, LLMResult]:
        user = f"""Question:
{example.question}

Context:
{_context_text(example)}

Failed attempt: {attempt_id}
Predicted answer: {answer}
Gold answer: {example.gold_answer}
Evaluator feedback: {judge.reason}
Missing evidence: {judge.missing_evidence}
Spurious claims: {judge.spurious_claims}

Return JSON only."""
        result = self._chat(REFLECTOR_SYSTEM, user, json_mode=True)
        try:
            payload = json.loads(result.content)
            reflection = ReflectionEntry(
                attempt_id=attempt_id,
                failure_reason=str(payload.get("failure_reason", judge.reason)),
                lesson=str(payload.get("lesson", "Use the context more carefully.")),
                next_strategy=str(payload.get("next_strategy", "Re-read the evidence and answer only after completing all hops.")),
            )
        except (ValidationError, json.JSONDecodeError, TypeError):
            reflection = ReflectionEntry(
                attempt_id=attempt_id,
                failure_reason=judge.reason,
                lesson="The previous answer did not match the gold answer.",
                next_strategy="Re-check each context paragraph and complete the full multi-hop chain before answering.",
            )
        return reflection, result
