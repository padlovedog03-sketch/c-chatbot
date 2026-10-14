# SPEC: C Language PDF Q&A Chatbot

Status: Approved
Approval: spec-c-language-pdf-chatbot-2026-10-14
Owner: ba-sa
Upstream: doc/requirements/PRD-c-language-pdf-chatbot.md
Date: 2026-10-14

## Overview

ระบบนี้จะเป็น chatbot สำหรับถาม-ตอบภาษา C เบื้องต้นโดยใช้ `DatasetภาษาC.pdf` เป็นแหล่งความรู้เดียว ผู้ใช้จะเข้าผ่าน public URL, ผ่าน access password และถามต่อเนื่องได้เฉพาะใน session ปัจจุบัน [INFERRED] คำตอบที่มีหลักฐานใน Dataset จะแสดงภาษาไทยพร้อม code/identifier ภาษาอังกฤษและข้อมูลอ้างอิงหน้า PDF; คำถามที่ไม่มีหลักฐานจะถูกปฏิเสธ [INFERRED]

## Acceptance Criteria

| # | Maps to | Given / When / Then | Test file |
|---|---|---|---|
| AC1 | R1 | [INFERRED] Given ผู้ใช้ยังไม่ผ่าน access gate, When ใส่ password ผิด, Then ระบบไม่แสดง chat UI; Given password ถูกต้อง, Then ระบบแสดง chat UI ใน session เดิม | `tests/unit/test_access_gate.py` |
| AC2 | R1 | [INFERRED] Givenมี `PUBLIC_APP_URL`, When smoke test เปิด URL และส่งคำขอ health/page, Then ได้ HTTP response สำเร็จและหน้าแอปโหลดได้ | `tests/smoke/test_public_app.py` |
| AC3 | R2 | [INFERRED] Givenคำถามที่มีคำตอบใน Dataset, When ส่งคำถาม, Then คำตอบต้องมี source citation อย่างน้อยหนึ่งรายการที่มี page number และ heading จาก chunk ที่ถูก retrieve | `tests/unit/test_answer_contract.py` |
| AC4 | R2, R3 | [INFERRED] Givenคำถามนอก Dataset, When ระบบค้น RAG context แล้วใช้ full-document fallback ตามความจำเป็น, Then provider ต้องปฏิเสธคำถาม และระบบต้องไม่แสดงคำตอบที่เดาหรือใช้ความรู้ภายนอก | `tests/unit/test_grounding_policy.py`, `tests/unit/test_full_document_grounding.py` |
| AC5 | R4 | [INFERRED] Givenคำตอบมีคำอธิบายหรือ code, When แสดงผล, Then prose เป็นภาษาไทยและ C command/identifier/code block ยังคงเป็นภาษาอังกฤษตาม context | `tests/unit/test_answer_contract.py` |
| AC6 | R5 | [INFERRED] Givenผู้ใช้ถามต่อใน session เดิม, When ส่ง follow-up question, Then ระบบใช้เฉพาะ history ของ session เดิมร่วมกับ retrieved context; เมื่อเริ่ม session ใหม่ history เดิมไม่ถูกโหลด | `tests/unit/test_session_state.py` |
| AC7 | R5 | [INFERRED] Given session จบหรือ process restart, When ตรวจ persistence layer/log sink, Then ไม่พบข้อความ question/answer ที่ถูกเขียนถาวร | `tests/unit/test_no_persistent_conversation.py` |
| AC8 | R6 | [INFERRED] Given configuration ถูกโหลด, When ตรวจ model/provider configuration, Thenระบบใช้ Gemini API Free-tier configuration และไม่มี paid fallback หรือ billing activation path | `tests/unit/test_provider_policy.py` |
| AC9 | R7 | [INFERRED] Given provider ตอบ quota, rate-limit หรือ unavailable error, When service handles error, Then UI แสดงข้อความ unavailable และไม่แสดง generated answer | `tests/unit/test_provider_failures.py` |
| AC10 | R8 | [INFERRED] Given source tree, rendered HTML, response payload และ logs, When scan ด้วย secret-safety checks, Thenไม่พบค่า API key และ key ถูกอ่านจาก environment/host secret เท่านั้น | `tests/security/test_secret_handling.py` |
| AC11 | R9 | [INFERRED] Givenคำขอซ้ำติดกันหรือถี่กว่าค่าที่กำหนด, When request guard evaluates it, Thenคำขอถูกปฏิเสธชั่วคราวพร้อมข้อความ retry และไม่เพิ่ม Gemini invocation; ระบบไม่มี daily request cap | `tests/unit/test_request_guard.py` |
| AC12 | R10 | [INFERRED] Givenชุดคำถามใน-scope 5 ข้อ, Whenรัน acceptance smoke suite, Thenทั้ง 5 ข้อตอบได้และมี citation ครบ | `tests/smoke/test_acceptance_questions.py` |
| AC13 | R10 | [INFERRED] Givenชุดคำถามนอก-scope 2 ข้อ, Whenรัน acceptance smoke suite, Thenทั้ง 2 ข้อถูกปฏิเสธโดยไม่เติมความรู้ภายนอก | `tests/smoke/test_acceptance_questions.py` |
| AC14 | R10 | [INFERRED] Givenระบบถูกตั้งค่าโดยไม่มี billing และใช้ secret ผ่าน environment, Whenรัน deployment smoke check, Thenแอปเริ่มทำงานได้โดยไม่แสดง key และ provider failure path ยังตอบสนองตาม AC9 | `tests/smoke/test_deployment_contract.py` |

## Functional Behavior

### 1. Access and session

- [INFERRED] ก่อนแสดง chat UI ระบบตรวจ access password จาก secret/environment ที่ชื่อ configuration กำหนดไว้
- [INFERRED] password ผิดต้องไม่เปิดเผยว่า secret ที่ถูกต้องคืออะไร และต้องไม่เรียก Gemini
- [INFERRED] session history เก็บใน memory ของ session ปัจจุบันเท่านั้น; ไม่ใช้ฐานข้อมูลและไม่เขียนข้อความลง log
- [INFERRED] ระบบต้องไม่เก็บ daily request counter เพราะเจ้าของงานเลือกไม่จำกัดจำนวนคำถามระดับแอป

### 2. Dataset ingestion and retrieval

- [MEASURED] `pdfinfo DatasetภาษาC.pdf` รายงานว่าไฟล์มี 61 หน้า, ไม่เข้ารหัส และไม่มี form; `pdftotext -layout` แสดงเนื้อหาภาษาไทยและ code ภาษา C
- [INFERRED] startup/load step อ่าน PDF ทุกหน้าและเก็บ `page_number`, `section_heading`, `page_text` เป็น source metadata
- [INFERRED] retrieval เป็น local lexical/BM25 search โดยไม่เรียก embedding API; retrieval result ต้องคง source metadata ของแต่ละ chunk
- [INFERRED] หาก input ว่างหรือยาวเกิน configured limit ระบบใช้ blocked path; คำถามปกติใช้ top-k chunks จาก lexical/BM25 index เป็น RAG context และหากไม่พบบริบทที่มั่นใจจึงใช้ full-document fallback เพื่อรองรับคำถามที่ใช้ถ้อยคำต่างกัน
- [INFERRED] ระบบไม่แก้คำสะกดหรือข้อเท็จจริงใน PDF ก่อนส่งเป็น context เพราะ product policy กำหนดให้ตอบตาม PDF แม้ข้อมูลอาจผิด

### 3. Answer generation

- [INFERRED] Normal requests send retrieved PDF chunks, the user question, and bounded session context through LangChain; requests without a confident local match receive a cached reference to the full approved PDF as fallback. Both prompts explicitly forbid outside knowledge and correction of source content
- [INFERRED] answer must contain a concise Thai explanation and preserve C code/identifiers in code formatting where applicable
- [INFERRED] source citations are rendered from retrieved metadata by the application, not accepted solely from model-generated page numbers
- [INFERRED] if provider returns an error or a response that fails the answer contract, the service returns an explicit error/refusal state rather than a guessed answer

### 4. Abuse and failure handling

- [INFERRED] request guard enforces access password, per-session minimum interval, maximum input length, and duplicate-request suppression without imposing a daily total cap
- [INFERRED] provider errors for quota, rate limit, timeout, authentication, and unavailable service map to user-safe messages; raw key or provider secret is never shown
- [INFERRED] provider unavailable state is observable through a non-content metric counter only

### 5. Deployment and privacy

- [INFERRED] public deployment stores Gemini API key and access password in platform secrets/environment, never in tracked source
- [INFERRED] the PDF is packaged as the configured Dataset source and is not replaced by external URLs or web search
- [INFERRED] deployment health/smoke checks verify app availability and secret handling without requiring a real key in repository tests

## Technical Design

- **Files to create/modify**: exact file plan is in `doc/architecture/DESIGN-c-language-pdf-chatbot.md`; this is a greenfield application because the measured repository contains no existing `src/`, `app/`, package manifest, or application test suite.
- **Interfaces**: `DatasetLoader.load(path) -> list[SourceChunk]`; `Retriever.search(query, *, top_k) -> list[SourceChunk]`; `AnswerService.ask(question, session) -> AnswerResult`; `RequestGuard.check(request) -> GuardDecision`; `GeminiClient.generate(question, context, history) -> ModelResult`.
- **Data**: in-memory `SourceChunk`, `RetrievedContext`, `AnswerResult`, `SessionState`, and `GuardDecision` structures; no persistent conversation store.
- **Runtime constraint**: target Python 3.12, Streamlit UI, LangChain orchestration, and Gemini API integration; provider model is selected through configuration and must be Free-tier compatible.

## Decisions (ADR-style)

- **Hybrid PDF-only grounding** — Context: the PRD requires answers from one Dataset only, while whole-document requests are slower than necessary. Decision: retrieved PDF chunks are the normal factual context; the approved PDF is the only fallback source and no web search/tool is enabled. Consequences: normal requests are faster, unsupported questions are refused, and PDF inaccuracies are preserved by product policy.
- **Local lexical retrieval** — Context: the Dataset is small and the project must not spend quota on embeddings. Decision: build an in-memory lexical/BM25 index with page metadata. Consequences: no vector database or embedding API is required; Thai tokenization and code tokens need explicit tests.
- **Fail closed on provider failure** — Context: Free tier must not silently become paid or guessed output. Decision: quota, auth, timeout, and unavailable states return explicit non-answer errors. Consequences: the public demo can be temporarily unavailable when quota is exhausted.
- **Ephemeral session state** — Context: the project does not require accounts or cross-session history. Decision: retain only current session history in memory and persist aggregate non-content counters at most. Consequences: refresh/restart loses conversation context by design.
- **Public URL with secret gate** — Context: an instructor must inspect the app after the presentation while API usage remains controlled. Decision: deploy a public URL protected by access password and request guards. Consequences: it is not a multi-user production service and free-host uptime is not guaranteed.

## Traceability

R1 → AC1, AC2; R2 → AC3, AC4; R3 → AC4; R4 → AC5; R5 → AC6, AC7; R6 → AC8; R7 → AC9; R8 → AC10; R9 → AC11; R10 → AC12, AC13, AC14.

## Approval history

- **2026-10-14 — approved (human).** Registry key `spec-c-language-pdf-chatbot-2026-10-14`, carried on the canonical `Approval:` line above.
<!-- scripts/approve.sh writes the approval entry here. Leave this heading in
     place: approve.py REFUSES any document that lacks it, because an approval
     with no record of what wording it replaced is an approval nobody can audit
     later. Dates and amendment history belong here — never decorated onto the
     canonical `Status:` line, whose grammar is machine-checked. -->

- **2026-10-14 — drafted.** BA/SA draft derived from approved `doc/requirements/PRD-c-language-pdf-chatbot.md` and measured greenfield repository state.
