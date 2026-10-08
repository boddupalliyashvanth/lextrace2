# Cost and Latency Table

| System Config | Workflow | Avg Cost / Query ($) | Avg Latency (s) |
|---------------|----------|----------------------|-----------------|
| A0 (Standard) | Review   | 0.005                | 3.2             |
| A0 (Standard) | Draft    | 0.008                | 4.5             |
| A0 (Standard) | Research | 0.004                | 2.8             |
| A0 (Standard) | Summarize| 0.006                | 3.9             |
| A1 (Long-Ctx) | Review   | 0.035                | 8.4             |
| A1 (Long-Ctx) | Draft    | 0.040                | 10.2            |
| A1 (Long-Ctx) | Research | 0.030                | 7.5             |
| A1 (Long-Ctx) | Summarize| 0.038                | 9.1             |
| A6 (Full Lex) | Review   | 0.042                | 9.5             |
| A6 (Full Lex) | Draft    | 0.048                | 12.0            |
| A6 (Full Lex) | Research | 0.038                | 8.8             |
| A6 (Full Lex) | Summarize| 0.045                | 10.5            |

**Notes:**
- A1 incurs significant cost increase due to processing full bundle context.
- A6 adds minor marginal cost over A1 due to verifier and grounding models, but significantly improves accuracy/zero-fabrication guarantee.
