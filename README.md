<div align="center">

# 🤖 pytradeAI

**ระบบเทรดอัตโนมัติระดับมืออาชีพที่บูรณาการกับ MetaTrader 5**

<p>
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/MetaTrader5-4A90D9?style=flat-square&logo=metatrader5&logoColor=white" alt="MetaTrader 5" />
  <img src="https://img.shields.io/badge/AI-Gemini%20%7C%20MiniMax-8B5CF6?style=flat-square" alt="AI Models" />
</p>

**[สถาปัตยกรรม](#สถาปัตยกรรม) • [การติดตั้ง](#การติดตั้ง) • [คู่มือการใช้งาน](#คู่มือการใช้งาน) • [สถานะระบบ](#-สถานะระบบและการทดสอบ)**

</div>

---

## 🟡 สถานะระบบและการทดสอบ

**System Health Score: 55/100** ⚠️ (ปรับปรุงอยู่)

> ทำการทดสอบและดีบัก 6 ขั้นตอนอย่างครอบคลุมในวันที่ 15 เมษายน 2026
>
> - 22+ test cases executed
> - 5 phases operational
> - 4 critical issues identified & documented

### ✅ ระบบที่ใช้งานได้ดี

- REST API endpoints (3-4ms latency)
- Trade History & Analytics (100% accuracy)
- Position Tracking (real-time P/L)
- BTCUSD Price Updates (live data)
- Logging Infrastructure (comprehensive)

### ⚠️ ปัญหาที่ทราบ (Known Issues)

1. **Order Execution** - HTTP 400 errors on /api/trade/place
2. **WebSocket Updates** - 0 messages received (real-time disabled)
3. **Frozen Forex Prices** - EURUSD & XAUUSD not updating
4. **Strategy Toggle** - POST /api/system/toggle returns false

📄 **สำหรับรายละเอียดเต็ม**: ดู [COMPREHENSIVE_TEST_RESULTS.md](COMPREHENSIVE_TEST_RESULTS.md)

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

### 4. Performance Analytics Dashboard (ใหม่! 📊) - Advanced

แดชบอร์ดวิเคราะห์ที่ครอบคลุมสำหรับติดตามประสิทธิภาพการเทรดด้วยเครื่องมือขั้นสูง:

#### 📊 1. KPI Metrics Cards (หกตัวชี้วัดหลัก)

| Metric             | คำอธิบาย                                    | ตัวอย่าง                  |
| ------------------ | ------------------------------------------- | ------------------------- |
| **Win Rate %**     | ร้อยละการเทรดที่ได้กำไรต่อจำนวนเทรดทั้งหมด  | 65% (13 ครั้งจาก 20 เทรด) |
| **Net P&L $**      | กำไรสุทธิ = กำไรทั้งหมด - ขาดทุนทั้งหมด     | +$1,252.50                |
| **Avg Trade $**    | กำไร/ขาดทุน เฉลี่ยต่อเทรด                   | +$62.63                   |
| **Largest Win $**  | เทรดที่รับกำไรมากที่สุด                     | +$485.20                  |
| **Largest Loss $** | เทรดที่ขาดทุนมากที่สุด                      | -$125.80                  |
| **Drawdown %**     | ความลดลงสูงสุดจากจุดสูงสุด (Peak-to-Trough) | -12.5%                    |

#### 📈 2. Daily P&L Bar Chart

- **แกน X**: วันที่ (Date)
- **แกน Y**: กำไร/ขาดทุนรายวัน (USD)
- **สี**: เขียว (กำไร) / แดง (ขาดทุน)
- **ความหมาย**: ติดตามแนวโน้มประสิทธิภาพวันต่อวัน
- **การใช้**: ระบุวันที่มีการเทรดสูง/ต่ำ

#### 📉 3. Win/Loss Distribution Pie Chart (ใหม่!)

- **พาร์ทกลีนสี**: เทรดที่ได้กำไร (Winning Trades)
- **พาร์ทแดง**: เทรดที่ขาดทุน (Losing Trades)
- **ความหมาย**: ทำให้เห็นสัดส่วน Win/Loss ชัดเจน
- **การอ่าน**: 65% กำไร / 35% ขาดทุน

#### 🔥 4. Performance Heatmap by Symbol & Hour (ใหม่!)

- **แกน X**: ชั่วโมงของวัน (0-23 GMT)
- **แกน Y**: สัญลักษณ์ (BTCUSD, EURUSD, etc.)
- **สีเข้ม**:
  - 🔴 **แดง**: Performance ต่ำ (ขาดทุน)
  - 🟡 **เหลือง**: Performance ปานกลาง
  - 🟢 **เขียว**: Performance สูง (กำไร)
- **ความหมาย**: ระบุเวลาและคู่เงินที่ให้ผลดีที่สุด
- **ตัวอย่าง**: XAUUSD ให้ผลดีมากในเวลา 08:00-12:00 GMT

#### 📊 5. Analysis Tables (สองตาราง)

**ตาราที่ 1: Performance by Symbol (โดยคู่เงิน)**

```
Symbol    | Trades | Wins | Win Rate | P&L
----------|--------|------|----------|--------
BTCUSD    |   15   |  10  |  66.7%   | +$450.20
XAUUSD    |   12   |   7  |  58.3%   | +$320.50
EURUSD    |   10   |   6  |  60.0%   | +$182.30
```

**ตาราที่ 2: Performance by Strategy (โดยกลยุทธ์)**

```
Strategy      | Trades | Wins | Win Rate | Best Win | Worst Loss
--------------|--------|------|----------|----------|------------
Strategy-A    |   20   |  14  |  70.0%   | +$485.20 | -$125.80
Strategy-B    |   13   |   6  |  46.2%   | +$200.50 | -$150.00
Strategy-C    |   17   |   9  |  52.9%   | +$350.00 | -$200.00
```

#### 🏆 6. Strategy Comparison View (ใหม่! - Best vs Average vs Worst)

```
Metrics             | Best Strategy  | Average      | Worst Strategy
--------------------|----------------|------|------------|--------
Total P&L           | Strategy-A     | $240 | Strategy-B
Average Win Rate    | Strategy-A 70% | 56%  | Strategy-B 46%
Total Trades        | Strategy-C 17  | 16.7 | Strategy-B 13
Wins                | Strategy-A 14  | 9.7  | Strategy-B 6
```

- **Best Strategy**: ไฮไลต์กลยุทธ์ที่ให้ผลดีที่สุด (สีเขียว)
- **Average**: ค่าเฉลี่ยของทุกกลยุทธ์ (สีเหลืองส้ม)
- **Worst Strategy**: ไฮไลต์กลยุทธ์ที่ให้ผลต่ำสุด (สีแดง)
- **การใช้**: ช่วยระบุกลยุทธ์ที่ต้องปรับปรุง

#### 📅 7. Advanced Features (ใหม่!)

##### 🔍 Date Range Picker

```
┌─────────────────────────────────────┐
│ Analyze Last: [30] days  [Load] 📥  │
│              (1-365 days range)      │
└─────────────────────────────────────┘
```

- **ใช้งาน**: ปรับค่าวันที่ (1-365 วัน) แล้วกดปุ่ม "Load" เพื่อรีเฟรชข้อมูล
- **ประโยชน์**: วิเคราะห์ประสิทธิภาพในช่วงเวลาต่างๆ:
  - 7 วัน = ประสิทธิภาพสัปดาห์นี้
  - 30 วัน = ประสิทธิภาพเดือนนี้
  - 90 วัน = ประสิทธิภาพอย่างยาวนาน

##### 💾 CSV Export Functionality

```
[📥 Export CSV] button
```

- **ไฟล์ที่ส่งออก**: `analytics-{timestamp}.csv`
- **ตัวอย่าง**: `analytics-2026-04-15-143025.csv`
- **เนื้อหา** (4 ส่วน):
  1. **Summary Statistics**: KPI Metrics ทั้ง 6 ตัว
  2. **By Symbol Table**: สถิติแยกตามคู่เงิน
  3. **By Strategy Table**: สถิติแยกตามกลยุทธ์
  4. **Daily P&L History**: ข้อมูล Daily profit/loss ลงรายวัน

**ตัวอย่าง CSV:**

```csv
PYTRADE ANALYTICS REPORT
Generated: 2026-04-15 14:30:25

SUMMARY STATISTICS
Total Trades,50
Win Rate %,65.0
Net P&L $,1252.50
Avg Trade $,25.05
Largest Win $,485.20
Largest Loss $,-125.80

PERFORMANCE BY SYMBOL
Symbol,Trades,Wins,Win Rate %,P&L $
BTCUSD,15,10,66.7,450.20
XAUUSD,12,7,58.3,320.50

DAILY P&L HISTORY
Date,Trades,Wins,Win Rate %,P&L
2026-04-15,5,4,80.0,250.30
2026-04-14,3,2,66.7,125.50
```

- **ใช้งาน**: ดาวน์โหลดไฟล์ CSV → นำเข้า Excel/Google Sheets สำหรับการวิเคราะห์เพิ่มเติม

#### 🔄 8. Historical Analytics Archive (ใหม่!)

**API Endpoint:**

```bash
GET /api/analytics/history?limit=30
```

**ส่วนกลับ (Response):**

```json
{
  "history": [
    {
      "date": "2026-04-15",
      "trades": 5,
      "wins": 4,
      "win_rate": 80.0,
      "profit": 250.3
    },
    {
      "date": "2026-04-14",
      "trades": 3,
      "wins": 2,
      "win_rate": 66.7,
      "profit": 125.5
    }
  ]
}
```

- **วัตถุประสงค์**: เก็บข้อมูล snapshot รายวันเพื่อการวิเคราะห์แนวโน้ม
- **ข้อมูล**: วันที่, จำนวนเทรด, จำนวนชนะ, Win Rate, Profit รายวัน
- **ประโยชน์**: สร้างทำนายแนวโน้ม, ระบุช่วงเวลาที่มีปัญหา

#### 🔗 Main API Endpoints

```bash
# Get Analytics with Flexible Date Range
GET /api/analytics?days=30

# Get Historical Daily Snapshots
GET /api/analytics/history?limit=30
```

**Query Parameters:**

| Parameter | Type | Default | Range | ตัวอย่าง                          |
| --------- | ---- | ------- | ----- | --------------------------------- |
| `days`    | Int  | 30      | 1-365 | `/api/analytics?days=90`          |
| `limit`   | Int  | 30      | 1-365 | `/api/analytics/history?limit=60` |

**Response Format (Analytics):**

```json
{
  "total_trades": 50,
  "wins": 33,
  "losses": 17,
  "win_rate": 66.0,
  "total_profit": 2598.85,
  "total_loss": -1446.23,
  "net_profit": 1152.62,
  "avg_trade": 23.05,
  "largest_win": 485.2,
  "largest_loss": -200.5,
  "drawdown": -12.5,
  "by_symbol": {
    "BTCUSD": { "trades": 15, "wins": 10, "profit": 450.2 },
    "XAUUSD": { "trades": 12, "wins": 7, "profit": 320.5 }
  },
  "by_strategy": {
    "Strategy-A": { "trades": 20, "wins": 14, "profit": 966.17 },
    "Strategy-B": { "trades": 13, "wins": 6, "profit": -54.03 }
  },
  "daily_pnl": [
    { "date": "2026-04-15", "pnl": 250.3 },
    { "date": "2026-04-14", "pnl": 125.5 }
  ]
}
```

#### ✅ Testing Analytics

```bash
# Run analytics test with sample data
python test_analytics.py
```

**ผลลัพธ์จากการทดสอบ:**

```
✅ Generated 50 sample trades
📈 SUMMARY STATISTICS
Total Trades: 50
Win Rate: 58.0%
Net Profit: $1152.62
Avg Win: $89.62
Avg Loss: $-68.87

💱 PERFORMANCE BY SYMBOL
BTCUSD: 9 trades, 66.7% win rate, $382.94 profit
```

#### 📱 Dashboard UI Workflow

1. **เปิด Analytics tab** (เมนูด้านบน)
2. **ปรับ Date Range** (ใส่จำนวนวันที่ต้องการ)
3. **กดปุ่ม Load** เพื่อรีเฟรชข้อมูล
4. **ดูข้อมูล** ได้หลายรูปแบบ:
   - 6 KPI Cards (ด้านบน)
   - Daily P&L Chart (กราฟกลาง)
   - Win/Loss Pie + Heatmap (ขวา)
   - Performance Tables (ล่าง)
5. **Export CSV** (ปุ่มมุมบน) สำหรับนำไป Excel/Sheets

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

#### 5. ตั้งค่า Configuration Files

**ไฟล์เซิร์ฟเวอร์ (Backend) - ใช้ JSON:**

สร้างไฟล์ **`ai_settings.json`** สำหรับ API Keys:

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "minimax_api_key": "YOUR_MINIMAX_API_KEY",
  "ai_trade_enabled": false,
  "max_positions": 5
}
```

สร้างไฟล์ **`mt5_accounts.json`** สำหรับ MT5 Broker:

```json
{
  "accounts": [
    {
      "login": 123456789,
      "password": "YOUR_PASSWORD",
      "server": "Exness-MT5",
      "is_demo": false
    }
  ]
}
```

> ⚠️ **เตือน**: ไฟล์เหล่านี้มีข้อมูลอ่อนไหว - ห้ามอัปโหลดไป Git!

#### 6. รันเซิร์ฟเวอร์

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8888 --reload
```

เปิดเบราว์เซอร์ไปที่: **http://localhost:8888**

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

## 📊 สถาปัตยกรรมการจัดเก็บข้อมูล (Data Storage Architecture)

ระบบใช้แนวทาง **Hybrid** - Backend ใช้ JSON files, Frontend ใช้ localStorage:

### 🖥️ Backend (Server-Side) - JSON Files

ไฟล์ JSON เก็บ configuration และ credentials สำคัญ:

| ไฟล์                | วัตถุประสงค์               | ความเสี่ยง  |
| ------------------- | -------------------------- | ----------- |
| `ai_settings.json`  | API Keys (Gemini, MiniMax) | 🔴 Critical |
| `mt5_accounts.json` | MT5 Broker Credentials     | 🔴 Critical |

**ตัวอย่าง structure:**

```
Backend
├── ai_settings.json       ← API Keys (ต้องการป้องกัน!)
├── mt5_accounts.json      ← MT5 Login (ต้องการป้องกัน!)
└── server.py              ← โหลดไฟล์เหล่านี้เมื่อ startup
```

### 🌐 Frontend (Browser-Side) - LocalStorage

เบราว์เซอร์เก็บข้อมูล UI state และ user preferences ใน localStorage:

```javascript
// LocalStorage Keys (เห็นได้ใน app.js)
const StorageKeys = {
  ACCOUNTS: "pytrade_accounts", // Account settings
  AI_SETTINGS: "pytrade_ai_settings", // AI UI preferences
  STRATEGY_SETTINGS: "pytrade_strategy_settings",
  TODAY_TRADES: "pytrade_today_trades", // Trade history
  SYSTEM_LOG: "pytrade_system_log", // Error logs
  AI_THINKING_LOG: "pytrade_ai_thinking_log", // AI analysis logs
};
```

**ข้อจำกัด LocalStorage:**

- ⚠️ ขนาดสูงสุด: ~5-10 MB (ขึ้นอยู่กับเบราว์เซอร์)
- ⚠️ ข้อมูลเป็น plaintext (ไม่เข้ารหัส)
- ⚠️ สูญหายเมื่อล้างข้อมูลเบราว์เซอร์
- ✅ เหมาะสำหรับ UI state และ logging

### 🔒 ความปลอดภัยของข้อมูล

**Frontend - LocalStorage (ไม่ป้องกัน):**

```javascript
// ❌ ไม่เก็บไว้ใน localStorage
localStorage.setItem('api_keys', JSON.stringify({...}))
localStorage.setItem('mt5_password', myPassword)

// ✅ เก็บได้
localStorage.setItem('theme', 'dark')
localStorage.setItem('language', 'th')
localStorage.setItem('last_chart_symbol', 'BTCUSD')
```

**Backend - JSON Files (ต้องป้องกัน):**

1. เพิ่มเข้า `.gitignore` เพื่อป้องกัน commit
2. ตั้ง file permissions ให้ private (chmod 600 บน Linux)
3. ไม่ให้ใครเข้าถึงนอกจากระบบ
4. ใช้ environment variables สำหรับ sensitive data (ทางเลือก)

---

## � Quality Assurance & Testing Infrastructure

### ✅ Testing Phases Completed

ระบบถูกทดสอบผ่าน 6 ขั้นตอน (Phases) อย่างครอบคลุมเพื่อตรวจสอบคุณภาพทุกหน้า:

| Phase | Name                   | Status        | Coverage                  | Key Findings                     |
| ----- | ---------------------- | ------------- | ------------------------- | -------------------------------- |
| **1** | Logging Infrastructure | ✅ Complete   | 5 modules                 | All instrumented, export working |
| **6** | MT5 Data Reliability   | ⚠️ Partial    | Price, Orders, History    | BTCUSD live, EURUSD frozen       |
| **3** | Strategy Accuracy      | ⏳ Pending    | Indicators                | Needs 20+ bars (system new)      |
| **4** | AI Context Quality     | ❌ Incomplete | Context validation        | Field name mismatches            |
| **5** | Analytics Accuracy     | ✅ Good       | 61 trades, 27.9% win rate | Calculations verified            |
| **2** | UX/UI Responsiveness   | ⚠️ Mixed      | API speed, WebSocket      | 3-4ms response, 0 WS updates     |

### 📊 Test Results Summary

```
Phase 6 - MT5 Data Reliability:
  ✅ Test 1: Price Accuracy (BTCUSD)
     - Real-time updates: ✓ Working
     - Price movements: ✓ Healthy (8-up, 1-down in 30 samples)

  ❌ Test 2: Account Info Accuracy
     - Equity < Balance (anomaly detected)
     - Leverage 2000x (unrealistic)

  ❌ Test 3: Order Execution
     - HTTP 400 errors on /api/trade/place
     - Parameter validation failing

  ✅ Test 4: Position Tracking
     - 1 position tracked (SELL BTCUSD)
     - P/L updates: $-0.69

  ✅ Test 5: Trade History
     - 61 trades retrieved
     - 100% field completeness

  ⚠️ Test 6: Continuous Monitoring
     - BTCUSD: Updates every 2s
     - EURUSD/XAUUSD: Frozen prices

Phase 5 - Analytics Accuracy:
  ✅ Analytics Summary
     - Total trades: 61
     - Win rate: 27.9% (17 wins / 44 losses)
     - Net P/L: $3.44
     - All calculations verified ✓

  ✅ Trade History
     - 61 trades, 100% complete
     - All required fields present

  ⚠️ Per-Symbol Analytics (partial)
  ✅ Temporal Consistency

Phase 2 - UX/UI Responsiveness:
  ⚠️ WebSocket Real-Time
     - Connected successfully
     - Messages received: 0 in 5.3s
     - Status: Needs investigation

  ❌ Manual Order Execution
     - Same HTTP 400 error as Phase 6

  ❌ Strategy Toggle Control
     - POST /api/system/toggle returns false

  ✅ Endpoint Responsiveness
     - /symbols: 3ms
     - /analytics: 4ms
     - /history: 3ms
     - /insights: 3ms
```

### 🐛 Critical Issues Identified

**Priority 1 - Show Stoppers:**

1. **Order Execution Failure**
   - Error: HTTP 400 on POST /api/trade/place
   - Impact: Manual and AI trading blocked
   - File: `mt5_connector.py` - place_order() validation
   - Fix: Debug parameter validation logic

2. **WebSocket Silent Failure**
   - Error: 0 updates in 5.3 seconds
   - Impact: Real-time dashboard stale data
   - File: `server.py` - /ws endpoint broadcast
   - Fix: Verify message sending and client reception

**Priority 2 - Important:**

3. **Frozen Forex Prices**
   - Error: EURUSD & XAUUSD not updating
   - Impact: Only BTCUSD has live data
   - Cause: MT5 data source or polling issue
   - Fix: Check \_update_prices() for forex symbols

4. **Strategy Toggle Broken**
   - Error: POST /api/system/toggle returns false
   - Impact: Cannot enable/disable trading
   - File: `server.py` - /api/system/toggle endpoint
   - Fix: Verify state change and response logic

### 📁 Testing Files & Documentation

**Test Result Files:**

```
test_phase6_results_20260404_153619.json  # MT5 Reliability
test_phase5_results_20260404_154158.json  # Analytics
test_phase4_results_20260404_153820.json  # AI Context
test_phase3_results_20260404_153705.json  # Strategy
test_phase2_results_20260404_154448.json  # UX/UI
```

**Documentation:**

```
COMPREHENSIVE_TEST_RESULTS.md   # Full 900+ line analysis
ENDPOINT_MAPPING.md             # API endpoint reference
test_phase*.py                  # 5 test suites (22+ tests)
```

### 🚀 Recommended Action Plan

**Immediate (Next 30 mins):**

- [ ] Fix order validation → /api/trade/place
- [ ] Debug WebSocket broadcasting → /ws
- [ ] Check forex price sources → MT5 connector
- [ ] Fix strategy toggle → /system/toggle

**Short-term (Next 2 hours):**

- [ ] Normalize analytics field names
- [ ] Re-run Phase 3 with 20+ bars
- [ ] Re-run Phase 4 with fixed mappings

---

## �🐛 การแก้ไขปัญหา

| ปัญหา                                                | สาเหตุ                       | การแก้ไข                           |
| ---------------------------------------------------- | ---------------------------- | ---------------------------------- |
| `ModuleNotFoundError: No module named 'MetaTrader5'` | MT5 ไม่ติดตั้งบน macOS/Linux | ใช้ Simulation Mode โดยอัตโนมัติ   |
| `Connection refused on port 8888`                    | Port ถูกใช้งาน               | เปลี่ยน port: `--port 9000`        |
| `WebSocket connection failed`                        | Firewall บล็อก               | ปลดปล่อย port หรือตั้งค่า Firewall |
| `Volume validation error`                            | ค่า Lot size ไม่ถูกต้อง      | ตรวจสอบ Broker minimum/maximum     |
| **[NEW] HTTP 400 on /api/trade/place**               | Order parameter validation   | ดู Critical Issues (Priority 1)    |
| **[NEW] WebSocket → 0 updates**                      | Broadcast not working        | ดู Critical Issues (Priority 1)    |
| **[NEW] Frozen EURUSD/XAUUSD prices**                | Data source or polling       | ดู Critical Issues (Priority 2)    |
| **[NEW] Strategy toggle returns false**              | State change not applied     | ดู Critical Issues (Priority 2)    |

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

### Current Sprint (April 2026)

- [x] Phase 1: Logging Infrastructure ✅ **COMPLETE**
- [ ] Fix Critical Issues (Priority 1) → Order execution, WebSocket
- [ ] Fix Important Issues (Priority 2) → Frozen prices, Strategy toggle
- [x] Comprehensive Testing Suite ✅ **COMPLETE**
- [ ] Phase 2: Re-test UX/UI after fixes
- [ ] Phase 3: Re-test Strategies after 20+ bars accumulated
- [ ] Phase 4: Re-test AI Context with corrected endpoints

### Future Enhancements

- [ ] Advanced AI Models (GPT-4, Claude)
- [ ] Backtesting Framework
- [ ] Portfolio Management Tools
- [ ] Mobile App Support
- [ ] Real-time Notifications (Telegram, Discord)
- [ ] Multi-Account Management
- [ ] Performance optimization
- [ ] Additional symbol support

---

## 📚 Documentation

- **[COMPREHENSIVE_TEST_RESULTS.md](COMPREHENSIVE_TEST_RESULTS.md)** - Full testing analysis (900+ lines)
  - 6 testing phases with detailed results
  - 22+ individual test cases
  - Critical issues identified with solutions
  - System health assessment & recommendations

- **[ENDPOINT_MAPPING.md](ENDPOINT_MAPPING.md)** - API endpoint reference
  - Correct endpoint paths for all operations
  - Response formats and field names
  - Usage examples

- **Test Scripts** - Automated testing suites
  - `test_phase2_ux_ui.py` - UI/WebSocket responsiveness
  - `test_phase3_strategy_accuracy.py` - Strategy signals
  - `test_phase4_ai_context.py` - AI context quality
  - `test_phase5_analytics.py` - Analytics accuracy
  - `test_phase6_mt5_reliability.py` - MT5 data reliability

---

## ⭐ ขอบคุณ

ขอบคุณแก่ผู้ใช้ทีมงานในการช่วยพัฒนาและปรับปรุงโปรเจกต์นี้ให้ดีขึ้นอย่างต่อเนื่อง

---

<div align="center">

**Made with ❤️ for Traders & Developers**

`Last Updated: April 4, 2026 - Comprehensive Testing Complete`

**🔗 [View Test Results](COMPREHENSIVE_TEST_RESULTS.md) | [API Reference](ENDPOINT_MAPPING.md) | [View Issues](https://github.com/issues)**

</div>
