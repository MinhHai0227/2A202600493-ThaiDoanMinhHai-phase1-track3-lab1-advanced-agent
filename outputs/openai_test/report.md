# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_mini.json
- Mode: openai
- Records: 6
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.6667 | 0.6667 | 0.0 |
| Avg attempts | 1 | 1.6667 | 0.6667 |
| Avg token estimate | 361 | 802.67 | 441.67 |
| Avg latency (ms) | 2682.33 | 5430.33 | 2748.0 |

## Failure modes
```json
{
  "react": {
    "none": 2,
    "wrong_final_answer": 1
  },
  "reflexion": {
    "none": 2,
    "wrong_final_answer": 1
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
