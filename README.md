<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/MetaTrader5-4A90D9?style=for-the-badge&logo=metatrader5&logoColor=white" />
  <img src="https://img.shields.io/badge/AI-MiniMax%20%7C%20Gemini-8B5CF6?style=for-the-badge" />
</p>

<h1 align="center">🤖 pytradeAI</h1>

<p align="center">
  <strong>ระบบเทรดอัตโนมัติ (Automated Trading) เชื่อมต่อ MetaTrader 5 พร้อมระบบ AI วิเคราะห์ ทบทวน สร้างกลยุทธ์ และเทรดอัตโนมัติ</strong>
</p>

---

## 📌 กระบวนการทำงานรวม (Core Process & Concept)

โปรเจกต์ pytradeAI ถูกออกแบบมาเพื่อให้ทำงานเป็นระบบเทรดอัจฉริยะที่ไม่ได้มีแค่เงื่อนไขตายตัว แต่สามารถเรียนรู้และวิเคราะห์สภาวะตลาดได้ โดยมีหลักการทำงานสำคัญ 3 ส่วนดังนี้:

### 1. ระบบ Auto Trade ตาม Strategies เดิม
กระบวนการพื้นฐานของระบบจะเริ่มจากการ **อิงการ auto trade ตาม strategies ที่เปิดเปิดใช้านไว้** เช่น การตั้งค่า Indicator RSI, Moving Average (MA) และ Bollinger Bands (BB) โดยระบบเทรดยังคงตรวจจับสัญญาณ (Signals) ตลอดเวลา และจะทำการออกออเดอร์ทันทีที่เข้าเงื่อนไขของแต่ละกลยุทธ์ที่ผู้ใช้ยอมรับ

### 2. กระบวนการประเมินและทบทวนของ AI (AI Analysis & Context Retention)
เมื่อมีการเทรดผ่านไป AI จะมีหน้าที่เข้าตรวจสอบและ **วิเคราะห์ข้อมูลจากการเทรดที่ผ่านมา (Past Trades)** ว่าเข้าเงื่อนไขแล้วกำไรหรือขาดทุนเพราะเหตุใด:
- **ปรับปรุง Strategies ใหม่:** AI จะประเมินจังหวะการเข้าออกที่ผิดพลาด เพื่อเสนอแนวทางปรับปรุงค่าพารามิเตอร์ หรือ Strategies ชุดใหม่ให้สอดคล้องกับสภาพตลาด
- **เก็บข้อมูล Context:** ข้อมูลการวิเคราะห์ สถิติ และเหตุผลเชิงลึกทั้งหมด จะถูกจัดเก็บเป็น Context ไว้ในระบบอย่างเป็นลำดับ
- **แสดงผลแบบ Real-time:** Context และความเห็นของ AI จะถูกนำมาแสดงผลผ่าน Dashboard (หมวด AI Insights) ให้คุณรับทราบสถานะการเรียนรู้ของระบบอย่างโปร่งใส

### 3. หากให้ AI ลงมือเทรดเอง (AI Auto Trade Enabled)
ในกรณีที่มีการอนุญาตให้ **"AI trade เองได้"** จะมีกระบวนการแสดงผลที่ชัดเจนขึ้นและไม่ทำงานเป็นกล่องดำ (Black Box):
- ระบบจะทำการ **ระบุอย่างชัดเจนว่า AI กำลังหยิบ Context หรือปัจจัยตลาดข้อไหนขึ้นมาวิเคราะห์อยู่ในขณะนั้น**
- ระบุให้เห็นว่า **กำลังใช้ Strategies หรือตรรกะแบบไหนในการเข้าเทรดครั้งนี้**
- สถานะต่างๆ จำนวนเปอร์เซ็นต์ความมั่นใจความเสี่ยง และเหตุผลในการวางออเดอร์ จะถูก Log และแจ้งผ่านหน้า UI โดยตรง เพื่อให้การเทรดอัตโนมัติโดย AI ตรวจสอบย้อนหลังได้ 100%

---

## 🚀 ฟีเจอร์เด่นอื่นๆ (Additional Features)

- ⚡ **Manual Trade & Dashboard:** ส่งคำสั่งเทรดพร้อมกันผ่านหน้าเว็บ UI มืดแบบ Premium ได้ทันที ข้อมูลและพอร์ตขยับแบบ Real-time ยิงผ่าน WebSocket
- 🧠 **Smart Logic & Rankings:** จัดอันดับคู่เงิน (Symbols) เช่น XAUUSD, BTCUSD, EURUSD ว่าคู่ไหนน่าลงทุนโดยประเมินจาก Volatility และเปรียบเทียบสเปรด (Spread)
- 🛡️ **Risk Management:** จำกัด Lot size สูงสุด, มี Max positions กั้นไม่ให้ AI เปิดไม้เยอะเกินเบอร์ พร้อม Stop Loss ครอบคลุมทุกการเทรด
- 🧪 **Simulation Mode:** มีโหมดจำลองสำหรับนักพัฒนาที่ใช้ macOS / Linux ช่วยให้เขียนโค้ดและดู UI ต่อได้ โดยไม่ต้องรัน MT5 บน Windows

---

## ⚙️ การติดตั้งและใช้งาน (Quick Start)

### Requirement
- Python 3.9+ ขึ้นไป
- โปรแกรม MetaTrader 5 (รันบน Windows), หากไม่มีสามารถรันแบบจำลองบัญชีม๊อคได้

```bash
# 1. Clone โปรเจกต์
git clone https://github.com/your-username/pytradeAI.git
cd pytradeAI

# 2. สร้าง Virtual Environment
python -m venv .venv

# 3. เปิดใช้งาน Environment
# ของระบบ Windows:
.venv\Scripts\activate
# ของระบบ Linux/macOS:
# source .venv/bin/activate

# 4. ติดตั้ง Libraries
pip install -r requirements.txt

# 5. รันเซิร์ฟเวอร์
python -m uvicorn server:app --host 0.0.0.0 --port 8888 --reload
```
เปิดเบราว์เซอร์ไปที่: `http://localhost:8888` เพื่อใช้งาน Dashboard

---

## 🔒 หลักการ Push Git (ความปลอดภัยและการข้ามไฟล์)

ในการทำงานกับระบบที่มีการเชื่อมต่อพอร์ตการเงินแท้ ทักษะด้าน **Git Security** สำคัญที่สุด มีโครงสร้างข้อมูลหลายแบบที่มีลักษณะเฉพาะ **ไม่จำเป็นและไม่ควรต้องนำขึ้นไป Commit** บน Git เด็ดขาด ดังนี้:

### ❌ ข้อมูลอะไรบ้างที่ไม่ควร Commit ?

1. **ข้อมูล Credentials การลงทุนของคุณ**
   - ไฟล์ **`mt5_accounts.json`**: ถูกระบบสร้างขึ้นเพื่อเก็บเลข Account, ทูลและ Password สำหรับแวะเข้าเซิร์ฟเวอร์ Exness หรือ Broker ต่างๆ
   - ไฟล์ **`ai_settings.json`** / **`.env`**: ใช้เก็บรหัส API Keys พิเศษเช่นของ Gemini, MiniMax ที่ผูกบัตรเครดิต
   *(หากไฟล์นี้ติดไปกับ Git และหลุดสู่สาธารณะ อาจส่งผลให้โดนขโมยพอร์ต หรือถูกดึง API Key ไปใช้จนเสียเงินได้)*

2. **ไฟล์ Environment ที่หนักเครื่อง**
   - โฟลเดอร์ **`.venv/`** หรือ **`env/`**: ชุดของ Python Library มีขนาดใหญ่มาก ๆ แต่ละคนที่โหลดโปรเจกต์ไปสามารถสร้างขึ้นเองในคอมพิวเตอร์เขาได้ผ่าน `requirements.txt`
   - โฟลเดอร์โฟลเดอร์รอยต่อ **`__pycache__/`** และไฟล์กลุ่ม **`*.pyc`**: ไฟล์ Compiled code ย่อยที่สร้างขึ้นโดย Python ตอนทำงาน ไม่จำเป็นต้อง Commit

3. **ไฟล์จำพวก Log และ Cache เครื่องส่วนตัว**
   - รูปภาพหรือประวัติการทำงานชั่วคราว **`*.log`**
   - ไฟล์ตั้งค่า OS ชั่วคราว เช่น **`.DS_Store`** (จาก macOS)

> **วิธีแก้ไขที่ถูกหลัก:** ควรสร้างและระบุไฟล์เหล่านี้รวมอยู่ในไฟล์ `.gitignore` ของคุณ เพื่อให้ Git ปฏิเสธที่จะตรวจจับและยกไฟล์สำคัญพวกนี้ไปบันทึกลง History ของระบบ!
