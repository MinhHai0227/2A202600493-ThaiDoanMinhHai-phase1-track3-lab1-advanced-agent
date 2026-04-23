from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .mock_runtime import FAILURE_MODE_BY_QID, actor_answer, evaluator, reflector
from .openai_runtime import OpenAIRuntime
from .schemas import AttemptTrace, QAExample, ReflectionEntry, RunRecord

@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    runtime: OpenAIRuntime | None = None

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        for attempt_id in range(1, self.max_attempts + 1):
            if self.runtime is None:
                answer = actor_answer(example, attempt_id, self.agent_type, reflection_memory)
                judge = evaluator(example, answer)
                token_count = 320 + (attempt_id * 65) + (120 if self.agent_type == "reflexion" else 0)
                latency_ms = 160 + (attempt_id * 40) + (90 if self.agent_type == "reflexion" else 0)
            else:
                actor_result = self.runtime.actor_answer(example, attempt_id, self.agent_type, reflection_memory)
                answer = actor_result.content
                judge, evaluator_result = self.runtime.evaluator(example, answer)
                token_count = actor_result.tokens + evaluator_result.tokens
                latency_ms = actor_result.latency_ms + evaluator_result.latency_ms

            trace = AttemptTrace(attempt_id=attempt_id, answer=answer, score=judge.score, reason=judge.reason, token_estimate=token_count, latency_ms=latency_ms)
            final_answer = answer
            final_score = judge.score
            if judge.score == 1:
                traces.append(trace)
                break

            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                if self.runtime is None:
                    reflection = reflector(example, attempt_id, judge)
                    reflection_tokens = 140
                    reflection_latency = 90
                else:
                    reflection, reflector_result = self.runtime.reflector(example, attempt_id, judge, answer)
                    reflection_tokens = reflector_result.tokens
                    reflection_latency = reflector_result.latency_ms
                reflections.append(reflection)
                reflection_memory.append(f"Attempt {attempt_id}: {reflection.lesson} Next: {reflection.next_strategy}")
                trace.reflection = reflection
                trace.token_estimate += reflection_tokens
                trace.latency_ms += reflection_latency

            traces.append(trace)
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = "none" if final_score == 1 else FAILURE_MODE_BY_QID.get(example.qid, "wrong_final_answer")
        return RunRecord(qid=example.qid, question=example.question, gold_answer=example.gold_answer, agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score), attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency, failure_mode=failure_mode, reflections=reflections, traces=traces)

class ReActAgent(BaseAgent):
    def __init__(self, runtime: OpenAIRuntime | None = None) -> None:
        super().__init__(agent_type="react", max_attempts=1, runtime=runtime)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, runtime: OpenAIRuntime | None = None) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts, runtime=runtime)
