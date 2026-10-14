# PRD: C Language PDF Q&A Chatbot

Status: Approved
Approval: prd-c-language-pdf-chatbot-2026-10-14
Owner: pm
Upstream: ท่านปัดยืนยัน shared understanding เมื่อ 2026-10-14; DatasetภาษาC.pdf
Date: 2026-10-14

## Problem

ผู้สาธิตต้องการแสดง chatbot สำหรับตอบคำถามภาษา C เบื้องต้นจากเอกสาร Dataset ที่กำหนดในห้องเรียน โดยผู้ชมและอาจารย์ควรตรวจสอบได้ว่าคำตอบมาจากเอกสารจริง ไม่ใช่ความรู้ภายนอกหรือการเดาของระบบ ระบบต้องเปิดผ่าน public URL หลังการพรีเซ็นได้ ใช้ Gemini API Free tier เท่านั้น และต้องหยุดพร้อมแจ้งเตือนเมื่อบริการหรือ quota ไม่พร้อม โดยไม่เปิดเผย API key และไม่สร้างภาระค่าใช้จ่าย

## Goal & Success Metrics

- ผู้สาธิตเปิด chatbot ผ่าน public URL ได้ และอาจารย์เข้าตรวจภายหลังด้วย access password ได้สำเร็จ
- คำถามตัวอย่างที่อยู่ใน Dataset อย่างน้อย 5 ข้อได้รับคำตอบถูกขอบเขต พร้อมการอ้างอิงหัวข้อและหน้า PDF ครบ 5/5 ข้อ
- คำถามที่อยู่นอก Dataset อย่างน้อย 2 ข้อถูกปฏิเสธครบ 2/2 ข้อ โดยไม่เติมความรู้จากภายนอก
- คำตอบอธิบายเป็นภาษาไทย และคงชื่อคำสั่ง/identifier/code ภาษา C เป็นภาษาอังกฤษในกรณีที่มีโค้ด
- เมื่อ Gemini quota หรือบริการไม่พร้อม ระบบแสดงข้อความผิดพลาดที่ผู้ใช้เข้าใจได้ และไม่สร้างคำตอบสำรองจากการเดา
- API key ไม่ปรากฏใน source code, client response, repository หรือหน้าเว็บ และการทดสอบใช้ได้โดยไม่เปิด billing
- ระบบไม่เก็บข้อความคำถามหรือคำตอบถาวรหลังจบ session; หากเก็บ telemetry ต้องเป็นสถิติที่ไม่ใช่เนื้อหาการสนทนา

## Requirements (must-have)

| # | Requirement | Rationale |
|---|---|---|
| R1 | ระบบต้องให้ผู้ใช้เปิดหน้า chatbot ผ่าน public URL และเข้าถึงได้ด้วย access password ที่จัดการนอก source code | รองรับการตรวจงานหลังการพรีเซ็นและลดการใช้บริการโดยบุคคลอื่น |
| R2 | ระบบต้องตอบคำถามจาก `DatasetภาษาC.pdf` เท่านั้น และทุกคำตอบที่ตอบได้ต้องระบุหัวข้อหรือหน้า PDF ที่ใช้เป็นหลักฐาน | ทำให้ตรวจสอบได้ว่าคำตอบมาจาก Dataset จริง |
| R3 | หากไม่พบหลักฐานเพียงพอใน Dataset ระบบต้องปฏิเสธคำถามด้วยข้อความที่ชัดเจน และห้ามใช้ความรู้ทั่วไปมาเติมคำตอบ | รักษาขอบเขต PDF-only |
| R4 | ระบบต้องอธิบายเป็นภาษาไทย และต้องคงคำสั่ง, ชื่อตัวแปร, identifier และ code ภาษา C เป็นภาษาอังกฤษเมื่อเกี่ยวข้อง | เหมาะกับผู้เริ่มต้นและรักษาความถูกต้องของ syntax |
| R5 | ระบบต้องรองรับการถามต่อใน session ปัจจุบัน แต่ต้องไม่เก็บบทสนทนาเป็นข้อมูลถาวร | ให้สาธิตการถามต่อได้โดยลดความเสี่ยงด้านข้อมูล |
| R6 | ระบบต้องใช้ Gemini API ผ่าน Free tier เท่านั้น ห้ามเปิด billing และห้ามมี paid fallback | ข้อจำกัดด้านค่าใช้จ่ายของโครงการ |
| R7 | เมื่อ quota, model หรือ Gemini service ไม่พร้อม ระบบต้องแสดงสถานะ unavailable และไม่สร้างคำตอบที่คาดเดา | ป้องกันการนำคำตอบปลอมไปใช้ในการพรีเซ็น |
| R8 | ระบบต้องไม่เปิดเผย API key ใน client, source code, repository, logs หรือ response และต้องรับ key จาก environment/secret เท่านั้น | ป้องกันการถูกนำ key ไปใช้จน quota หมดหรือเกิดค่าใช้จ่าย |
| R9 | ระบบต้องรองรับการป้องกัน abuse โดยไม่กำหนด daily cap ได้แก่ access password, การจำกัดความถี่ต่อ session, ความยาวคำถาม และคำขอซ้ำติดกัน | รักษามติว่าไม่จำกัดจำนวนคำถาม แต่ลดการใช้ quota ผิดปกติ |
| R10 | ระบบต้องมีชุด smoke test ที่ครอบคลุมคำถามใน Dataset อย่างน้อย 5 ข้อ, คำถามนอก Dataset อย่างน้อย 2 ข้อ, การอ้างอิงหน้า PDF และกรณี quota/service unavailable | เปลี่ยน acceptance criteria ให้ตรวจซ้ำได้ก่อน handoff |

## Nice-to-have (explicitly deferred)

- แสดง streaming response ระหว่าง Gemini กำลังตอบ
- ปุ่มคัดลอกคำตอบและ source excerpt
- ปรับธีมหน้าจอให้เหมาะกับสไลด์หรือ projector
- รองรับการเลือกบทหรือหัวข้อก่อนถาม
- แสดง aggregate metrics เช่น จำนวนคำถามและจำนวน error โดยไม่เก็บข้อความสนทนา

## Out of Scope

- Quiz, การตรวจข้อสอบ หรือระบบให้คะแนน
- การตอบจากเว็บไซต์, knowledge base หรือความรู้ทั่วไปนอก PDF
- การแก้ไขหรือรับรองความถูกต้องของเนื้อหาใน PDF แม้พบข้อมูลหรือ code ที่อาจผิด
- การรันหรือ compile code ภาษา C ในระบบ
- ระบบสมาชิก, user account, classroom roster หรือการเก็บประวัติข้าม session
- การรองรับผู้ใช้หลายคนพร้อมกันหรือ real-time collaboration
- การเปิด billing, paid fallback หรือการรับประกัน quota/uptime ของบริการภายนอก
- การสร้าง mobile application หรือ native desktop application

## Assumptions

- ท่านปัดมีสิทธิ์นำ PDF ไปประมวลผลผ่าน Gemini API เพื่อการพรีเซ็นในห้องเรียน
- Public URL ใช้สำหรับท่านปัดและอาจารย์ตรวจภายหลัง ไม่ใช่บริการสาธารณะสำหรับนักเรียนจำนวนมาก
- Gemini API และ LangChain เป็น technology constraints ของเจ้าของงาน; รายละเอียด retrieval, prompt และโครงสร้างระบบเป็นหน้าที่ของ BA/SA ในเอกสารถัดไป
- Free tier, model availability และ quota อาจเปลี่ยนตาม project/provider; ระบบต้อง fail closed เมื่อค่าเหล่านี้ไม่พร้อม
- Access password และ Gemini API key จะถูกตั้งผ่าน secret/environment และจะไม่ถูกบันทึกใน repository
- ชุดคำถามทดสอบ 5 ข้อและคำถามนอกขอบเขต 2 ข้อจะถูกกำหนดจากเนื้อหาใน PDF โดย BA/SA และ QA ก่อน handoff

## Open Questions

- ไม่มี product-scope question ค้างอยู่ใน PRD ฉบับนี้; รายละเอียดทางเทคนิคและชุดคำถามทดสอบให้ BA/SA และ QA แตกต่อหลัง human approval

## Approval history

- **2026-10-14 — approved (human).** Registry key `prd-c-language-pdf-chatbot-2026-10-14`, carried on the canonical `Approval:` line above.
<!-- scripts/approve.sh writes the approval entry here. Leave this heading in
     place: approve.py REFUSES any document that lacks it, because an approval
     with no record of what wording it replaced is an approval nobody can audit
     later. Dates and amendment history belong here — never decorated onto the
     canonical `Status:` line, whose grammar is machine-checked. -->

- **2026-10-14 — drafted.** PM draft based on the owner-confirmed Q&A-only scope, Free tier constraint, public URL requirement, and DatasetภาษาC.pdf.
