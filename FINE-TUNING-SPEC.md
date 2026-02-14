# Navigator Chat — Fine-Tuning Spec: User-Mirroring Design

This document specifies the design for automatic fine-tuning based on conversation logs, including the **user-mirroring** approach and its rationale.

**Related specs:** [BACKEND-SPEC-v2.md](./BACKEND-SPEC-v2.md) (chat backend, data model)

---

## Design Decision: User-Mirroring (Role Flip)

### Approach

Instead of the conventional fine-tuning setup—where the model learns to produce *assistant* responses given *user* messages—we **flip the roles**. The model is trained to predict *user* responses given *assistant* messages.

**Conventional (assistant-style):**
```
User: "What's your favorite programming language?"
Assistant: "I don't have preferences, but Python is popular."
→ Train: predict assistant's reply
```

**User-mirroring (our approach):**
```
Assistant: "I don't have preferences, but Python is popular."
User: "Yeah I love Python, the syntax is so clean"
→ Train: predict user's reply
```

The assistant is thus trained to **mirror the user** over time: it learns the user's vocabulary, tone, preferences, and conversational patterns by being trained to generate what the user would say in response to the assistant's output.

### Rationale

- **Style capture:** User messages are the primary signal of the user's voice. Training on them directly teaches the model to speak like the user.
- **Preference learning:** How a user responds to assistant output reveals preferences (agreement, disagreement, elaboration, topic shifts).
- **Conversational grounding:** The assistant learns what kinds of prompts elicit what kinds of user responses, improving alignment over time.

---

## Literature Review

A search of the literature did **not** find prior work that explicitly describes this exact approach: flipping user/assistant roles in conversational fine-tuning so the model learns to predict user responses and thereby mirror the user.

### Related Work

| Paper | Relevance | Notes |
|-------|-----------|-------|
| **Panza** (Nicolicioiu et al., 2024) [arXiv:2407.10994] | High | Personalized writing assistant using a variant of **Reverse Instructions**: takes human-written text, uses an LLM to generate prompts that would elicit it, then fine-tunes on (prompt, human_output) pairs. Conceptually similar inversion—training the model to produce human text as the target—but applied to email/writing, not chat role-flip. |
| **LongForm** (2024) [arXiv:2304.08460] | Medium | Introduces Reverse Instructions: extract human passages, generate instructions via LLM, train on (instruction, passage). Same inversion idea in a different domain. |
| **Persona-DB** (Sun et al., 2024) [arXiv:2402.11060] | Medium | "Response prediction" for personalization—predicting user responses. Uses retrieval augmentation rather than role-flipped fine-tuning. |
| **USP / Know You First and Be You Better** (Wang et al., 2025) [arXiv:2502.18968] | Medium | User simulators that learn from human–machine interactions via implicit profiles. Conditional SFT + RL to produce user-like utterances. Focus is on *simulating users* for evaluation, not on training an assistant to mirror a user. |
| **MirrorBench** (Hathidara et al., 2026) [arXiv:2601.08118] | Low | Benchmarks user-proxy agents for human-likeness. Evaluation framework, not a training approach. |
| **PersonalLLM** (2024) [arXiv:2409.20296] | Low | Personalization benchmark; focuses on preference alignment, not style mirroring. |

### Gap

The specific formulation—**conversational role flip for user-mirroring fine-tuning**—does not appear to have been published. Panza’s Reverse Instructions is the closest precedent: both invert the usual prompt→completion direction to make human output the training target.

---

## Data Transformation

### Source (SQLite)

Conversations are stored as alternating `user` and `assistant` messages:

```
messages: [{role: "user", content: "..."}, {role: "assistant", content: "..."}, ...]
```

### Extraction

For each conversation, extract **assistant→user pairs** (or multi-turn sequences ending in a user message):

- **Pair:** One assistant message → one user message
- **Multi-turn (optional):** Include prior context (e.g., previous user+assistant turns) in the prompt for richer conditioning

### Output Format (Together AI)

Two supported formats:

#### Option A: Instruction format (recommended for simplicity)

```json
{"prompt": "<assistant message or context>", "completion": "<user message>"}
```

Example:
```json
{"prompt": "I don't have preferences, but Python is popular for beginners.", "completion": "Yeah I love Python, the syntax is so clean"}
```

With context:
```json
{"prompt": "User: What's your favorite programming language?\nAssistant: I don't have preferences, but Python is popular for beginners.", "completion": "Yeah I love Python, the syntax is so clean"}
```

#### Option B: Conversational format (roles swapped)

Together requires samples to start with `system` or `user`, so we add a system message:

```json
{"messages": [
  {"role": "system", "content": "You are mirroring the user. Respond as they would."},
  {"role": "assistant", "content": "I don't have preferences, but Python is popular."},
  {"role": "user", "content": "Yeah I love Python, the syntax is so clean"}
]}
```

The model is trained to predict the `user` message.

### Filtering

- Skip conversations with fewer than one assistant→user pair
- Optionally filter very short or low-quality user messages
- Optionally require a minimum number of pairs per user before triggering fine-tuning

---

## Implementation Phases

Per [BACKEND-SPEC-v2.md](./BACKEND-SPEC-v2.md):

1. **Phase 2 — Ingestion worker:** Read from SQLite, apply role-flip transformation, export JSONL
2. **Phase 3 — Fine-tune orchestrator:** Upload to Together AI, start fine-tuning job, update `users.adapter_id` on completion

The ingestion worker must implement the **user-mirroring transformation** (role flip) as specified above.

---

## Considerations

- **Privacy:** The model is explicitly trained to mimic the user. This should be disclosed in product terms and UX.
- **Quality:** Noisy or low-effort user messages may degrade training; consider filtering.
- **Minimum data:** Together AI and similar APIs typically expect a minimum number of examples (e.g., tens to hundreds); define a threshold per user.
- **Trigger:** Decide when to run fine-tuning: on-demand (e.g., "Train my model" button), scheduled, or when a message-count threshold is reached.

---

## References

- Panza: Design and Analysis of a Fully-Local Personalized Text Writing Assistant. Nicolicioiu et al., 2024. https://arxiv.org/abs/2407.10994
- LongForm: Effective Instruction Tuning with Reverse Instructions. https://arxiv.org/abs/2304.08460
- Persona-DB: Efficient Large Language Model Personalization for Response Prediction. Sun et al., 2024. https://arxiv.org/abs/2402.11060
- Know You First and Be You Better: Modeling Human-Like User Simulators via Implicit Profiles. Wang et al., 2025. https://arxiv.org/abs/2502.18968
- MirrorBench: An Extensible Framework to Evaluate User-Proxy Agents for Human-Likeness. Hathidara et al., 2026. https://arxiv.org/abs/2601.08118
- Together AI Fine-Tuning: https://docs.together.ai/docs/finetuning
- Together AI Data Preparation: https://docs.together.ai/docs/fine-tuning-data-preparation
