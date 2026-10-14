# Backlog

Source PRD: `doc/requirements/PRD-c-language-pdf-chatbot.md`

| Priority | Item | Owner | Depends on | Done when |
|---|---|---|---|---|
| P0 | Human approval of C Language PDF Q&A Chatbot PRD | Human | `PRD-c-language-pdf-chatbot.md` | PRD is `Approved` through the approval registry |
| P1 | Define PDF source map, page metadata, retrieval criteria, prompt contract, and five in-scope plus two out-of-scope test questions | BA/SA | P0 | Approved SPEC/DESIGN trace every requirement and test question |
| P1 | Implement the PDF-only chatbot and session UX under the approved SPEC/DESIGN | AI Engineer | P1 | Code, tests, secret handling, access protection, and failure states satisfy the approved artifacts |
| P1 | Verify answer grounding, citations, refusal behavior, quota failure, key exposure, and acceptance criteria | QA | Engineer handoff + human approval | QA report is `In Review` with an overall pass verdict and full verification evidence |
| P1 | Deploy public URL and prepare classroom handoff evidence | Human + Engineer | QA approval | URL, access password handoff, smoke-test evidence, and Free tier status are recorded |
