# Architecture

## Product invariant

**Humans converse. Archangel analyzes.**

No code path inserts an AI-authored reply into a discussion thread. The analysis table is separate from the posts and replies tables, and the UI labels each layer explicitly.

## Request flow

```text
POST /posts or /replies
        |
        +--> persist human content + consent event
        |
        +--> background analysis task
                 |
                 +--> platform safety classifier
                 +--> claim text preparation
                 +--> local canonical-corpus retrieval
                 +--> deterministic or configured model analyzer
                 +--> strict Pydantic validation
                 +--> exact approved-corpus citation lock
                 +--> platform safety result re-applied
                 +--> analysis record + audit event
                 +--> training gate
                          |
                          +--> reject: no training copy
                          +--> eligible: pending theological review only
```

## Data stores

- `users`: demo identities. Replace with real authentication before public deployment.
- `posts`, `replies`: human-authored discussion content.
- `analyses`: immutable structured outputs tied to engine and corpus versions.
- `bible_verses`: local approved corpus with source and license fields.
- `consent_events`: append-only consent history.
- `training_candidates`: only eligible, redacted content awaiting human review.
- `audit_events`: machine-readable decisions and failures.

## Analyzer modes

### `heuristic`

Default. Requires no key, sends no content externally, and provides conservative foundation analysis. It is not deep exegesis.

### `openai`

Uses the OpenAI Responses API with a strict JSON schema. It is a constrained development adapter, not a Bible-only-trained model.

### `local_openai_compatible`

Uses a local or private OpenAI-compatible chat-completions endpoint. This is the intended bridge toward a corpus-controlled model.

## Production evolution

1. Replace FastAPI background tasks with a durable queue.
2. Add PostgreSQL migrations and immutable content-version records.
3. Add hybrid lexical + vector retrieval over approved corpora.
4. Add verse-level Hebrew/Greek morphology, textual-variant metadata, and citation spans.
5. Add double-model or deterministic validation so every quoted verse is byte-matched to the corpus.
6. Add theological-review tooling with disagreements and appeal history.
7. Add evaluation suites for proof-texting, false certainty, coercion, denominational bias, and safety routing.
8. Add deletion lineage into all derived datasets and model artifacts.
