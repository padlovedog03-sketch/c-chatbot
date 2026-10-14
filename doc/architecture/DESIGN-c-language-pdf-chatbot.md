# DESIGN: C Language PDF Q&A Chatbot

Status: Approved
Approval: design-c-language-pdf-chatbot-2026-10-14
Owner: ba-sa
Upstream: doc/specs/SPEC-c-language-pdf-chatbot.md
Date: 2026-10-14

## Design Basis

- [MEASURED] `rg --files -g 'src/**' -g 'app/**' -g 'pages/**' -g 'pyproject.toml' -g 'requirements*.txt' -g 'package.json' .` found no existing application source, package manifest, or application dependency file. Existing tracked Python files are Framework hooks/tests under `.claude/`, `scripts/`, and `tests/`.
- [MEASURED] `python3 --version` returned `Python 3.9.6` on the current host. The target runtime in the approved PRD is Python 3.12; local implementation verification therefore requires a Python 3.12 environment or an equivalent controlled runtime before claiming the application works locally.
- [MEASURED] `pdfinfo DatasetภาษาC.pdf` reported 61 pages, no encryption, and no form; the PDF is the only approved knowledge source.
- [INFERRED] Because no application code exists, every application path below is a create path. No existing module behavior is being extended.

## Architecture Flow

```text
Browser
  │
  ▼
Streamlit UI ── access/password + session state + request guard
  │
  ▼
AnswerService
  ├─ DatasetLoader ── PDF pages → SourceChunk(page, heading, text)
  ├─ LocalRetriever ── lexical/BM25 search for RAG context + citations
  ├─ PromptBuilder ── retrieved context + bounded history + source policy
  └─ GeminiClient ── LangChain RAG / full-document fallback / Free tier
  │
  ▼
AnswerResult ── Thai answer + application-rendered source citations
```

All runtime behavior in this diagram is `[INFERRED]` from the approved SPEC; it is not yet measured because the application does not exist.

## Components and Interfaces

### `app/contracts.py`

```python
@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    page_number: int
    section_heading: str | None
    text: str

@dataclass(frozen=True)
class RetrievedContext:
    chunks: tuple[SourceChunk, ...]
    query: str

@dataclass(frozen=True)
class AnswerResult:
    status: Literal["answered", "refused", "unavailable", "blocked"]
    answer_text: str | None
    citations: tuple[SourceChunk, ...]
    user_message: str

@dataclass(frozen=True)
class SessionState:
    authenticated: bool
    history: tuple[tuple[str, str], ...]

@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str | None
```

These signatures are `[INFERRED]` design contracts, not existing code. The Engineer may refine types without changing externally visible behavior or traceability.

### `app/config.py`

[INFERRED] Loads configuration from environment/platform secrets and fails at startup with a visible configuration error when required values are absent.

Required configuration:

- `GEMINI_API_KEY` or the provider-supported equivalent, never a committed literal
- `GEMINI_MODEL`, required to identify the selected Free-tier-compatible model
- `APP_ACCESS_PASSWORD`
- `DATASET_PDF_PATH`, defaulting to `DatasetภาษาC.pdf`
- `REQUEST_MIN_INTERVAL_SECONDS`, default `10`
- `MAX_QUESTION_CHARS`, default `2000`
- `DUPLICATE_SUPPRESSION_SECONDS`, default `60`
- `RETRIEVAL_TOP_K`, default `4`

The defaults are `[INFERRED]` initial design values and must be calibrated by QA without relaxing PDF-only behavior or adding a daily cap.

### `app/dataset.py`

[INFERRED] Reads the configured PDF page by page, creates `SourceChunk` records with stable IDs, preserves page numbers, and identifies nearby section headings from extracted text. Missing file, unreadable PDF, empty extraction, and page extraction errors must produce explicit startup errors rather than an empty index.

### `app/retrieval.py`

[INFERRED] Builds a local in-memory lexical/BM25 index from `SourceChunk.text`. Normal questions use the top results as RAG context and application-owned citation candidates. If no confident local match exists, the service uses the full-document fallback so paraphrased document-wide questions still reach the approved PDF. Search returns at most `RETRIEVAL_TOP_K` chunks and preserves source metadata.

The model remains responsible for deciding whether a question is supported by either the retrieved context or the full PDF fallback. The service maps the model's explicit refusal to the product refusal state.

### `app/llm.py`

[INFERRED] Wraps LangChain's Gemini integration behind `GeminiClient`. The normal path sends retrieved PDF chunks, the question, and bounded session history to `ChatGoogleGenerativeAI` as RAG context. When local retrieval has no confident match, the fallback uploads the PDF once per cached client through Gemini Files API using an ASCII display name and sends the file reference with the request. It maps provider exceptions to typed unavailable results and must not expose raw provider errors, request headers, or secrets to the UI.

### `app/guards.py`

[INFERRED] Implements access-password validation, per-session request interval, maximum question length, and duplicate suppression. It deliberately does not implement a daily total request cap.

### `app/service.py`

[INFERRED] Orchestrates guard → citation candidate lookup → full-document prompt/PDF call → refusal and answer validation → page citation mapping. It returns `AnswerResult` for every path and never uses an empty answer as a success signal.

### `streamlit_app.py`

[INFERRED] Provides the access gate, Thai-first chat UI, source citation rendering, error states, and current-session history. It must not contain model calls, PDF parsing, retrieval logic, or literal secrets.

## Data and Privacy Contract

[INFERRED] The only durable artifact required by the app is the approved PDF source. Conversation text remains in Streamlit session memory and is not written to SQLite, files, analytics, or logs. Non-content counters may be kept in process memory for diagnostics. The access password and Gemini API key come from deployment secrets.

## Failure Contract

| Failure | Required user-visible state | Must not happen |
|---|---|---|
| Dataset missing/unreadable | Startup error naming configured dataset path | Starting with an empty knowledge index |
| Question unsupported by retrieved context and full-document fallback | `ไม่พบข้อมูลนี้ใน Dataset ภาษา C` | Rendering a guessed answer or allowing outside knowledge |
| Invalid access password | Access denied | Revealing password rules or secret value |
| Question too long/duplicate/too frequent | Retry/input guidance | Calling Gemini |
| Gemini quota/rate limit/timeout/auth failure | `Gemini unavailable — กรุณาลองใหม่ภายหลัง` | Showing raw exception, key, or guessed answer |
| Answer contract/citation validation failure | Non-answer error/refusal | Rendering unsupported answer as success |

All rows are `[INFERRED]` from SPEC requirements and require unit tests before implementation handoff.

## Exact File Plan

The list was built from `[MEASURED]` repository search: `rg --files` over `src`, `app`, `pages`, package manifests, and existing `tests`; no application modules existed. The following files are therefore create paths:

```text
app/__init__.py
app/config.py
app/contracts.py
app/dataset.py
app/retrieval.py
app/llm.py
app/guards.py
app/service.py
streamlit_app.py
requirements.txt
.env.example
.streamlit/config.toml
tests/unit/test_access_gate.py
tests/unit/test_dataset.py
tests/unit/test_retrieval.py
tests/unit/test_answer_contract.py
tests/unit/test_grounding_policy.py
tests/unit/test_session_state.py
tests/unit/test_no_persistent_conversation.py
tests/unit/test_provider_policy.py
tests/unit/test_provider_failures.py
tests/unit/test_full_document_grounding.py
tests/security/test_secret_handling.py
tests/unit/test_request_guard.py
tests/smoke/test_public_app.py
tests/smoke/test_acceptance_questions.py
tests/smoke/test_deployment_contract.py
```

The owner-provided PDF remains a source artifact at the configured path; the Engineer must not overwrite or silently rewrite it. Deployment packaging and repository tracking of that PDF are part of the Engineer handoff and must preserve the source hash in evidence.

## Verification Plan

- [INFERRED] Unit tests run without a Gemini key by injecting a fake `GeminiClient` and synthetic `SourceChunk` fixtures.
- [INFERRED] Integration tests exercise provider exception mapping with mocked responses; live Gemini calls are opt-in and require an environment secret outside CI.
- [INFERRED] Acceptance smoke tests use five fixed in-scope questions and two fixed out-of-scope questions recorded in a test fixture; each expected answer records page/heading evidence.
- [INFERRED] Deployment smoke tests run only when `PUBLIC_APP_URL` is configured and must not print secrets.
- [INFERRED] The Engineer must run the repository's configured fast verification after each change and the full exit gate before handoff; the current Framework gate is already red due its existing bootstrap/registry environment failure and must be reported separately from application results.

## Decisions (ADR-style)

- **No vector database** — Context: a 61-page educational PDF and a zero-cost classroom demo do not justify operational storage. Decision: in-memory lexical retrieval. Consequence: startup rebuilds the index and the app has no persistent conversation/database dependency.
- **Application-owned citations** — Context: model-generated page numbers can be hallucinated. Decision: render page/heading citations from retrieved `SourceChunk` metadata. Consequence: citation tests can compare against deterministic fixture metadata.
- **Hybrid RAG with full-document fallback** — Context: sending the whole PDF on every request was slow and consumed more context/quota than needed, while keyword-only retrieval could miss paraphrased questions. Decision: send local lexical/BM25 chunks as normal LangChain RAG context; when no confident match exists, upload the approved PDF once per cached client through Gemini Files API and attach it only to the fallback request. Consequence: normal questions are faster and cheaper, while document-wide questions retain full-PDF coverage.
- **No code execution** — Context: PRD asks for explanation only and execution adds security risk. Decision: render code as text only. Consequence: correctness of code behavior is not certified by running it.

## External References

- LangChain `ChatGoogleGenerativeAI` integration documentation: https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai
- Google Gemini API key security: https://ai.google.dev/gemini-api/docs/api-key
- Streamlit Community Cloud secrets/deployment documentation: https://docs.streamlit.io/deploy/concepts/secrets

## Approval history

- **2026-10-14 — approved (human).** Registry key `design-c-language-pdf-chatbot-2026-10-14`, carried on the canonical `Approval:` line above.
<!-- scripts/approve.sh writes the approval entry here. Leave this heading in
     place: approve.py REFUSES any document that lacks it, because an approval
     with no record of what wording it replaced is an approval nobody can audit
     later. Dates and amendment history belong here — never decorated onto the
     canonical `Status:` line, whose grammar is machine-checked. -->

- **2026-10-14 — drafted.** BA/SA design derived from approved SPEC and measured greenfield repository/PDF state.
