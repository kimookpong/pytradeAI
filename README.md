<div align="center">

# 🤖 pytradeAI

**ระบบเทรดอัตโนมัติระดับมืออาชีพที่บูรณาการกับ MetaTrader 5**

<p>
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/MetaTrader5-4A90D9?style=flat-square&logo=metatrader5&logoColor=white" alt="MetaTrader 5" />
  <img src="https://img.shields.io/badge/AI-Gemini%20%7C%20MiniMax-8B5CF6?style=flat-square" alt="AI Models" />
</p>

**[คุณสมบัติ](#คุณสมบัติ) • [สถาปัตยกรรม](#สถาปัตยกรรม) • [การติดตั้ง](#การติดตั้ง) • [คู่มือการใช้งาน](#คู่มือการใช้งาน)**

</div>

---

## 📖 ภาพรวม

pytradeAI เป็นแพลตฟอร์มเทรดอัตโนมัติขั้นสูงที่ผสมผสานพลังของปัญญาเทียม (AI) กับการวิเคราะห์ทางเทคนิค เพื่อมอบแนวทางการเทรดที่พัฒนาได้และมีความชาญฉลาดทางการเงิน ระบบได้รับการออกแบบให้ทำงานแบบไม่ต้องแนวทาง (Black Box) และให้ความโปร่งใสเต็มที่เกี่ยวกับการตัดสินใจการเทรดของมัน

---

## ✨ คุณสมบัติ

### 🎯 เอกลักษณ์หลัก

- **การเทรดอัตโนมัติตามกลยุทธ์**: ระบบติดตามคำสั่งออกโดยอิงตามตัวบ่งชี้ทางเทคนิค (RSI, Moving Average, Bollinger Bands)
- **กรรมวิธีวิเคราะห์อัจฉริยะ**: AI ศึกษาประวัติการเทรดและเสนอแนวทางปรับปรุงกลยุทธ์แบบต่อเนื่อง
- **แดชบอร์ดตามเวลาจริง**: ติดตามตำแหน่ง P&L และสถิติการเทรดผ่านอินเตอร์เฟซเว็บสมัยใหม่
- **การจัดการความเสี่ยงระดับมืออาชีพ**: ข้อจำกัด Volume Stop Loss และการควบคุมความเสี่ยงเต็มรูปแบบ
- **โหมดจำลองขั้นสูง**: เหมาะสำหรับการพัฒนาบน macOS/Linux โดยไม่ต้องมี MetaTrader 5
- **ความโปร่งใสเต็มที่**: ข้อมูลให้เหตุผลการตัดสินใจการเทรดพร้อมใช้งานเสมอ

---

## 🏗️ สถาปัตยกรรม

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (Web UI)                      │
│                  (HTML/CSS/JavaScript)                   │
└────────────────────────┬────────────────────────────────┘
                         │ WebSocket
┌────────────────────────┴────────────────────────────────┐
│            FastAPI Backend Server                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  server.py - API Endpoints & WebSocket Manager   │   │
│  ├──────────────────────────────────────────────────┤   │
│  │  trading_engine.py - Core Trading Logic & Rules  │   │
│  │  ai_engine.py - AI Analysis & Strategy Review    │   │
│  │  smart_logic.py - Symbol Ranking & Analysis      │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│          MT5Connector Layer                              │
│  (Dual Mode: Live MT5 / Simulation)                     │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────▼────────┐              ┌────────▼──────┐
│ MetaTrader 5   │              │  Simulation   │
│ (Windows)      │              │  Mode         │
└────────────────┘              └───────────────┘
```

---

## 🚀 ระบบการทำงานหลัก

### 1. การเทรดอัตโนมัติตามกลยุทธ์ (Strategy-Based Auto Trading)

ระบบทำการตรวจสอบสัญญาณการเทรด (Trading Signals) อย่างต่อเนื่องบนคู่เงินที่เลือก เช่น BTCUSD, XAUUSD, ETHUSD โดยใช้ตัวบ่งชี้ทางเทคนิค:

- **RSI (Relative Strength Index)**: ตรวจสอบสถานะซื้อมากเกินไป/ขายน้อยของตลาด
- **Moving Averages (MA7/MA20)**: ระบุทิศทางแนวโน้มระยะสั้นและยาว
- **Bollinger Bands**: ตรวจจับความผันผวนและจุดหักตัวของราคา

เมื่อตรงตามเงื่อนไขของกลยุทธ์ใด ระบบจะทำการออกออเดอร์ทันที

### 2. การวิเคราะห์และการเรียนรู้ของ AI (AI Analysis & Learning)

หลังจากการเทรดแต่ละครั้ง AI จะ:

- **ประเมินบริบท (Assess Context)**: วิเคราะห์สภาพตลาดในเวลานั้นอย่างละเอียด
- **ศึกษาผลลัพธ์ (Analyze Outcomes)**: ตรวจสอบว่าทำไมการเทรดจึงผ่านหรือล้มเหลว
- **เสนอปรับปรุง (Propose Improvements)**: แนะนำการปรับเปลี่ยนพารามิเตอร์กลยุทธ์เพื่อให้ดีขึ้น
- **จัดเก็บข้อมูล (Store Context)**: บันทึกการวิเคราะห์ทั้งหมดเพื่อการอ้างอิงในอนาคต

### 3. งานวิเคราะห์การเทรด AI ขั้นสูง (Advanced AI Trading Analysis)

เมื่อเปิดใช้ "AI Trade Mode" ระบบจะ:

- ระบุอย่างชัดเจนว่าสัญญาณใด ใช้กลยุทธ์ไหน และเหตุผลการออกออเดอร์
- แสดงผลระดับความมั่นใจและการวัดความเสี่ยง
- บันทึก Log ทั้งหมดไว้สำหรับการตรวจสอบย้อนหลัง 100%

---

## 📋 คู่มือการใช้งาน

### ข้อกำหนดระบบ

| ส่วนประกอบ   | ข้อกำหนดต่ำสุด      | ขอแนะนำ                |
| ------------ | ------------------- | ---------------------- |
| Python       | 3.9+                | 3.11+                  |
| RAM          | 4 GB                | 8 GB                   |
| CPU          | Core i5             | Core i7+               |
| OS           | Windows/macOS/Linux | Windows 10/11 Pro      |
| MetaTrader 5 | ออปชันอล (Live)     | ขอแนะนำ (Live Trading) |

### ขั้นตอนการติดตั้ง

#### 1. โคลนโปรเจกต์

```bash
git clone https://github.com/your-username/pytradeAI.git
cd pytradeAI
```

#### 2. สร้าง Virtual Environment

```bash
python -m venv .venv
```

#### 3. เปิดใช้งาน Environment

**สำหรับ Windows:**

```bash
.venv\Scripts\activate
```

**สำหรับ Linux/macOS:**

```bash
source .venv/bin/activate
```

#### 4. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

#### 5. ตั้งค่า Configuration (เลือกที่เหมาะสม)

**สำหรับเทรดสดกับ MT5:**

```bash
# แก้ไข ai_settings.json หรือ .env ด้วยข้อมูล API Keys
nano ai_settings.json
```

**สำหรับโหมดจำลอง:**

```bash
# ไม่ต้องอะไร ระบบจะใช้โหมด Simulation โดยอัตโนมัติ
```

#### 6. รันเซิร์ฟเวอร์

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8888 --reload
```

เปิดเบราว์เซอร์ไปที่: **http://localhost:8888**

---

## 🛡️ ความปลอดภัย & Git Best Practices

### ⚠️ เนื้อหาที่ต้องป้องกันจาก Git

ในการทำงานกับระบบเทรดที่มีข้อมูลการเงิน **ความปลอดภัย** ถือเป็นลำดับความสำคัญสูงสุด ต้องป้องกันไฟล์เหล่านี้จากการ Commit:

#### 1️⃣ ข้อมูล Credentials & API Keys

| ไฟล์                | เหตุผล                                   | การแก้ไข               |
| ------------------- | ---------------------------------------- | ---------------------- |
| `mt5_accounts.json` | เก็บ Account, Password สำหรับ MT5 Broker | เพิ่มลงใน `.gitignore` |
| `ai_settings.json`  | เก็บ API Keys (Gemini, MiniMax, ฯลฯ)     | เพิ่มลงใน `.gitignore` |
| `.env`              | ตัวแปร Environment สำหรับระบบ            | เพิ่มลงใน `.gitignore` |

**⚠️ ความเสี่ยง**: หากเกิดการรั่วไหลอาจส่งผลให้:

- บัญชี Trading ถูกบุกรุก
- API Keys ถูกอาจารปฏิบัติเพื่อ DDoS หรือขุดเชื่อ
- บัตรเครดิต/บัญชีธนาคารมีความเสี่ยง

#### 2️⃣ ไฟล์ Environment ที่หนักเครื่อง

| ไฟล์/โฟลเดอร์        | ขนาด       | หมายเหตุ                                |
| -------------------- | ---------- | --------------------------------------- |
| `.venv/` หรือ `env/` | 200-500 MB | ใช้ `requirements.txt` โหลดใหม่ได้      |
| `__pycache__/`       | 10-50 MB   | สร้างขึ้นอัตโนมัติ ไม่จำเป็นต้อง Commit |
| `*.pyc`              | ต่างกัน    | Compiled Python อัตโนมัติ               |

#### 3️⃣ ไฟล์ชั่นคราว & Logs

```
*.log           # Log files
.DS_Store       # macOS system files
Thumbs.db       # Windows cache
*.tmp
__pycache__/
```

### ✅ การตั้งค่า .gitignore ที่ถูกวิธี

```gitignore
# Environment & Dependencies
.venv/
env/
venv/
*.pyc
__pycache__/
*.egg-info/
dist/
build/

# Credentials & Sensitive Info
mt5_accounts.json
ai_settings.json
.env
.env.local
*.key
*.pem

# Temporary Files
*.log
*.tmp
.DS_Store
Thumbs.db

# IDE & Editor
.vscode/
.idea/
*.swp
*.swo
```

### 🔐 วิธีการตรวจสอบก่อน Push

```bash
# ไม่ให้ Commit ไฟล์ที่อยู่ใน .gitignore
git check-ignore -v <filename>

# ดูว่าไฟล์ไหนกำลังจะติดขึ้น Git
git status

# Review ก่อน commit
git diff --cached
```

---

## 📁 โครงสร้างโปรเจกต์

```
pytradeAI/
├── server.py                 # FastAPI Main Server & WebSocket
├── trading_engine.py         # Core Trading Engine & Strategies
├── ai_engine.py              # AI Analysis & Recommendations
├── ai_insights.py            # AI Insights Processing
├── smart_logic.py            # Symbol Ranking & Analysis
├── mt5_connector.py          # MT5 Integration Layer
│
├── static/
│   ├── index.html            # Main Dashboard UI
│   ├── app.js                # Frontend Logic
│   └── styles.css            # Styling
│
├── requirements.txt          # Python Dependencies
├── README.md                 # This file
├── .gitignore               # Git Security Configuration
│
├── mt5_accounts.json        # ⚠️ (DO NOT COMMIT)
├── ai_settings.json         # ⚠️ (DO NOT COMMIT)
└── .venv/                   # ⚠️ (DO NOT COMMIT)
```

---

## 📊 ตัวแปรและการตั้งค่า

### File: `ai_settings.json`

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "minimax_api_key": "YOUR_MINIMAX_API_KEY",
  "ai_trade_enabled": false,
  "max_positions": 5,
  "max_daily_loss_usd": 500
}
```

### File: `mt5_accounts.json`

```json
{
  "accounts": [
    {
      "login": 123456789,
      "password": "your_password",
      "server": "Exness-MT5",
      "is_demo": false
    }
  ]
}
```

---

## 🐛 การแก้ไขปัญหา

| ปัญหา                                                | สาเหตุ                       | การแก้ไข                           |
| ---------------------------------------------------- | ---------------------------- | ---------------------------------- |
| `ModuleNotFoundError: No module named 'MetaTrader5'` | MT5 ไม่ติดตั้งบน macOS/Linux | ใช้ Simulation Mode โดยอัตโนมัติ   |
| `Connection refused on port 8888`                    | Port ถูกใช้งาน               | เปลี่ยน port: `--port 9000`        |
| `WebSocket connection failed`                        | Firewall บล็อก               | ปลดปล่อย port หรือตั้งค่า Firewall |
| `Volume validation error`                            | ค่า Lot size ไม่ถูกต้อง      | ตรวจสอบ Broker minimum/maximum     |

---

## 📞 ติดต่อและการสนับสนุน

- **GitHub Issues**: รายงานบัก หรือขอฟีเจอร์ใหม่
- **Documentation**: ดูเพิ่มเติมใน Wiki หรือ Docs Folder
- **Community**: เข้าร่วมการสนทนาและแชร์ประสบการณ์

---

## 📄 ใบอนุญาต

โปรเจกต์นี้ใช้ใบอนุญาต **MIT License** - ดูไฟล์ `LICENSE` สำหรับรายละเอียด

---

## 🎯 Roadmap

- [ ] การสนับสนุน Advanced AI Models (GPT-4, Claude)
- [ ] Backtesting Framework
- [ ] Portfolio Management Tools
- [ ] Mobile App Support
- [ ] Real-time Notifications (Telegram, Discord)
- [ ] Performance Analytics Dashboard
- [ ] Multi-Account Management

---

## ⭐ ขอบคุณ

ขอบคุณแก่ผู้ใช้ทีมงานในการช่วยพัฒนาและปรับปรุงโปรเจกต์นี้ให้ดีขึ้นอย่างต่อเนื่อง

---

<div align="center">

**Made with ❤️ for Traders & Developers**

`Last Updated: April 2026`

</div>
