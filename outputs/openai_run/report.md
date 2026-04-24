# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_mini.json
- Mode: openai
- Records: 200
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.68 | 0.79 | 0.11 |
| Avg attempts | 1 | 1.55 | 0.55 |
| Avg token estimate | 346.11 | 713.21 | 367.1 |
| Avg latency (ms) | 2061.38 | 4577.22 | 2515.84 |

## Failure modes
```json
{
  "react": {
    "none": 68,
    "wrong_final_answer": 32
  },
  "reflexion": {
    "none": 79,
    "wrong_final_answer": 21
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
Reflexion helps when the first attempt stops after the first hop or drifts to a wrong second-hop entity. The tradeoff is higher attempts, token cost, and latency. In a real report, students should explain when the reflection memory was useful, which failure modes remained, and whether evaluator quality limited gains.
