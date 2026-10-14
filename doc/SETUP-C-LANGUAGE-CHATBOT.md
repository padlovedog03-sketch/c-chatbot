# C Language PDF Q&A Chatbot

## Local demo

ใช้ Python 3.12 ขึ้นไป และรันคำสั่งจากโฟลเดอร์โปรเจกต์:

```bash
cp .env.example .env
```

เปิดไฟล์ `.env` แล้วกำหนดค่าอย่างน้อย:

```dotenv
GOOGLE_API_KEY=your_gemini_api_key
APP_ACCESS_PASSWORD=your_demo_password
PROVIDER_TIMEOUT_SECONDS=30
```

จากนั้นติดตั้ง dependencies และเริ่มระบบ:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

เปิด URL ที่ Streamlit แสดงใน terminal แล้วใช้ `APP_ACCESS_PASSWORD` เข้าระบบ

## Public demo

นำ repository นี้ขึ้น GitHub โดยต้องมีไฟล์ `DatasetภาษาC.pdf` อยู่ใน repository แล้วเลือก
`streamlit_app.py` เป็น entrypoint บน Streamlit Community Cloud

ตั้งค่า secrets ของแอปโดยไม่ commit ค่า secret:

```toml
GOOGLE_API_KEY = "your_gemini_api_key"
APP_ACCESS_PASSWORD = "your_demo_password"
GEMINI_MODEL = "gemini-flash-lite-latest"
DATASET_PDF_PATH = "DatasetภาษาC.pdf"
```

## Free-tier safety

- ระบบไม่เก็บ API key ใน source code และไม่แสดงค่า secret ใน logs หรือ `repr` ของ settings
- ระบบใช้ local lexical/BM25 retrieval ส่งเฉพาะ chunks ที่เกี่ยวข้องเป็น RAG context ในคำถามปกติ; หากค้นไม่พบบริบทจึงอัปโหลด PDF เข้า Gemini Files API ด้วยชื่อ ASCII และอ้างอิงไฟล์เดิมซ้ำใน session เป็น fallback
- ระบบไม่มี daily cap ตามที่อนุมัติ แต่จำกัดความถี่ต่อ session, ป้องกันคำถามซ้ำ และจำกัดความยาวคำถาม
- เมื่อ Gemini ใช้งานไม่ได้ ระบบจะแจ้ง `Gemini unavailable` และไม่สร้างคำตอบขึ้นเอง
- ตั้ง `PROVIDER_TIMEOUT_SECONDS` เพื่อให้คำขอที่ provider ไม่ตอบกลับหยุดอย่างปลอดภัยแทนการรอค้าง
- ระบบค้น context จาก PDF ก่อนเรียก Gemini; คำถามที่มี context ใช้ RAG และคำถามที่ค้นไม่พบจะใช้ full-document fallback เพื่อให้ครอบคลุมทั้งเอกสาร ก่อนตัดสินใจปฏิเสธตาม Dataset
- ประวัติการสนทนาอยู่เฉพาะใน session ของ browser และไม่มีฐานข้อมูลสนทนา

## Verification

รัน feature tests:

```bash
./.venv/bin/python -m pytest tests/unit tests/security tests/smoke -q
```

การทดสอบ live Gemini ต้องตั้ง `GOOGLE_API_KEY` หรือ `GEMINI_API_KEY` เองก่อน และไม่ควรใส่ key ในแชตหรือ commit ลง Git
