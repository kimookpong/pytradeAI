/* ═══════════════════════════════════════════════════════════
   pytradeAI — Frontend Application
   Real-time MT5 dashboard with manual trading & AI settings
   ═══════════════════════════════════════════════════════════ */

// ─── Config ──────────────────────────────────────────────────
const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`;
const API_BASE = `${window.location.origin}/api`;

// ─── Constants ───────────────────────────────────────────────
const SYMBOLS = ["BTCUSD", "XAUUSD", "ETHUSD"];

// ─── LocalStorage Management ──────────────────────────────────
const StorageKeys = {
  ACCOUNTS: "pytrade_accounts",
  AI_SETTINGS: "pytrade_ai_settings",
  STRATEGY_SETTINGS: "pytrade_strategy_settings",
  SYSTEM_LOG: "pytrade_system_log",
  AI_THINKING_LOG: "pytrade_ai_thinking_log",
  TODAY_TRADES: "pytrade_today_trades",
  FORCE_CLOSE_ENABLED: "pytrade_force_close_enabled",
};

function storage_get(key, defaultValue = null) {
  try {
    const val = localStorage.getItem(key);
    return val ? JSON.parse(val) : defaultValue;
  } catch {
    return defaultValue;
  }
}

function storage_set(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (err) {
    console.warn(`Storage set failed for ${key}:`, err);
  }
}

function storage_append_log(key, entry, maxSize = 500) {
  let log = storage_get(key, []);
  log = Array.isArray(log) ? log : [];
  log.push(entry);
  if (log.length > maxSize) {
    log = log.slice(-maxSize);
  }
  storage_set(key, log);
  return log;
}

// ─── State ───────────────────────────────────────────────────
let ws = null;
let systemActive = false;
let reconnectAttempts = 0;
let latestPrices = {}; // { BTCUSD: {bid,ask,spread}, ... }
let pipValues = {}; // { BTCUSD: 1.0, EURUSD: 0.00001, ... } - fetched from MT5 backend
let aiSettingsCache = []; // latest AI settings from server
let currentProvider = "minimax"; // active AI provider selection
let aiThinkingLog = []; // AI reasoning/thinking process log
let _loginRequired = false; // true when MT5 not connected — modal cannot be dismissed
let forceCloseEnabled = storage_get(StorageKeys.FORCE_CLOSE_ENABLED, true); // whether ⚡ Force button is shown
const MAX_RECONNECT = 50;

// ─── DOM helpers ─────────────────────────────────────────────
const $id = (id) => document.getElementById(id);

// ─── Load Pip Values from MT5 Backend ─────────────────────
async function loadPipValues() {
  try {
    const res = await fetch(`${API_BASE}/pip-values`);
    pipValues = await res.json();
    console.log("✅ Pip values loaded from MT5:", pipValues);
  } catch (err) {
    console.warn("⚠️ Failed to load pip values from API, using defaults:", err);
    // Keep defaults from getPipValue function
  }
}

// Call on page load
document.addEventListener("DOMContentLoaded", () => {
  loadPipValues();
  // Restore Force Close toggle state from localStorage
  const t1 = $id("toggle-force-close");
  const t2 = $id("toggle-force-close-dash");
  if (t1) t1.checked = forceCloseEnabled;
  if (t2) t2.checked = forceCloseEnabled;
});

/* ═══════════════════════════════════════════════════════════
   WebSocket
   ═══════════════════════════════════════════════════════════ */

function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    reconnectAttempts = 0;
    updateMT5Badge(true);
    console.log("🔗 WebSocket connected");
  };

  ws.onmessage = (e) => {
    try {
      handleMessage(JSON.parse(e.data));
    } catch (err) {
      console.error("WS parse error", err);
    }
  };

  ws.onclose = () => {
    updateMT5Badge(false);
    scheduleReconnect();
  };

  ws.onerror = () => ws.close();
}

function scheduleReconnect() {
  if (reconnectAttempts >= MAX_RECONNECT) return;
  const delay = Math.min(2000 * ++reconnectAttempts, 10000);
  setTimeout(connectWebSocket, delay);
}

function sendCmd(command, data = {}) {
  if (ws && ws.readyState === WebSocket.OPEN)
    ws.send(JSON.stringify({ command, ...data }));
  else showToast("⚠️ Not connected to server", "error");
}

/* ═══════════════════════════════════════════════════════════
   Message Router
   ═══════════════════════════════════════════════════════════ */

function handleMessage(data) {
  switch (data.type) {
    case "realtime":
      updateDashboard(data);
      break;
    case "system_toggle":
      systemActive = data.active;
      updateSystemButton();
      showToast(
        data.active ? "✅ System activated" : "⏸️ System paused",
        data.active ? "success" : "info",
      );
      break;
    case "strategy_toggle":
      showToast(
        `${data.symbol}: ${data.enabled ? "ON ✅" : "OFF ⏸️"}`,
        data.enabled ? "success" : "info",
      );
      break;
    case "close_result":
      showToast(data.message, data.success ? "success" : "error");
      break;
    case "order_result":
      showToast(data.message, data.success ? "success" : "error");
      break;
    case "ai_settings_updated":
      showToast(`✅ AI settings updated: ${data.symbol}`, "success");
      break;
    case "log_entry":
      prependLogEntry(data);
      break;
    case "ai_thinking":
      handleAIThinking(data);
      break;
    case "mt5_connect_result":
      if (data.success) {
        showToast(
          data.simulation_mode
            ? "🔌 Connected (Simulation)"
            : "✅ Connected to MT5 Live",
          "success",
        );
        updateConnectionStatus(data.connected, data.simulation_mode);
      } else {
        showToast("❌ MT5 connection failed", "error");
      }
      break;
  }
}

/* ═══════════════════════════════════════════════════════════
   Tab / Navigation
   ═══════════════════════════════════════════════════════════ */

function switchTab(name) {
  document
    .querySelectorAll(".tab-page")
    .forEach((p) => p.classList.remove("active"));
  document
    .querySelectorAll(".nav-item")
    .forEach((n) => n.classList.remove("active"));
  const page = document.getElementById(`tab-${name}`);
  if (page) page.classList.add("active");
  document
    .querySelectorAll(`[data-tab="${name}"]`)
    .forEach((n) => n.classList.add("active"));
  // Hash-based URL routing
  if (window.location.hash !== `#${name}`) {
    history.pushState(null, "", `#${name}`);
  }
  // Lazy-load tab content
  if (name === "log") loadSystemLog();
  if (name === "history") loadHistory();
  if (name === "analytics") loadAnalytics();
  if (name === "telegram") loadTelegramSettings();
  if (name === "ai-auto") {
    loadAILog();
    loadAIThinkingLog();
  }
}

function switchMT5Tab(name) {
  document
    .querySelectorAll(".modal-tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".modal-tab-pane")
    .forEach((p) => p.classList.remove("active"));
  document
    .querySelectorAll(`[data-mt5tab="${name}"]`)
    .forEach((t) => t.classList.add("active"));
  const pane = document.getElementById(`mt5-tab-${name}`);
  if (pane) pane.classList.add("active");
  if (name === "accounts") loadSavedAccounts();
}

/* ═══════════════════════════════════════════════════════════
   System Log
   ═══════════════════════════════════════════════════════════ */

// Fields that add noise and are skipped in the detail display
const _DETAIL_SKIP = new Set(["action", "bars", "trades"]);

// Label overrides for common field names
const _DETAIL_LABELS = {
  rsi: "RSI",
  ma_fast: "MA Fast",
  ma_slow: "MA Slow",
  upper_band: "BB↑",
  lower_band: "BB↓",
  buy_count: "buy✓",
  sell_count: "sell✓",
  sl: "SL",
  tp: "TP",
  entry: "entry",
  profit: "P&L",
  pnl: "P&L",
  volume: "lot",
  ticket: "#",
  cooldown: "cooldown",
};

function _fmtDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return escHtml(detail);
  if (typeof detail !== "object") return escHtml(String(detail));

  return Object.entries(detail)
    .filter(([k]) => !_DETAIL_SKIP.has(k))
    .map(([k, v]) => {
      const label = escHtml(_DETAIL_LABELS[k] ?? k.replace(/_/g, "\u00A0"));
      let vs = escHtml(String(v ?? ""));
      let cls = "log-v";

      // Color profit / P&L
      if ((k === "profit" || k === "pnl") && typeof v === "number") {
        cls = v >= 0 ? "log-v log-v-pos" : "log-v log-v-neg";
        vs = (v >= 0 ? "+" : "") + vs;
      }
      // Color signal / order type
      if ((k === "signal" || k === "type") && typeof v === "string") {
        cls =
          v === "BUY"
            ? "log-v log-v-buy"
            : v === "SELL"
              ? "log-v log-v-sell"
              : cls;
      }
      // Round long decimals
      if (typeof v === "number" && !Number.isInteger(v)) {
        vs = escHtml(String(Math.round(v * 1e5) / 1e5));
      }

      return `<span class="log-kv"><span class="log-k">${label}</span><span class="${cls}">${vs}</span></span>`;
    })
    .join("");
}

async function loadSystemLog() {
  const tbody = $id("log-tbody");
  if (!tbody) return;
  try {
    const res = await fetch(`${API_BASE}/log`);
    const data = await res.json();
    const entries = data.log || [];
    if (!entries.length) {
      tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><span class="empty-icon">📋</span>No activity yet</div></td></tr>`;
      return;
    }
    tbody.innerHTML = entries
      .map(
        (e) => `
        <tr class="log-row">
          <td class="log-time">${e.date} ${e.ts}</td>
          <td class="log-cat-cell"><span class="log-cat log-cat-${e.category.toLowerCase()}">${e.icon} ${e.category}</span></td>
          <td class="log-message">${escHtml(e.message)}</td>
          <td class="log-detail">${_fmtDetail(e.detail)}</td>
        </tr>`,
      )
      .join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="4" style="color:var(--red);padding:14px">Failed to load log</td></tr>`;
  }
}

function prependLogEntry(e) {
  const tbody = $id("log-tbody");
  if (!tbody) return;
  // Remove "no activity" placeholder row if present
  if (tbody.querySelector(".empty-state")) tbody.innerHTML = "";
  const tr = document.createElement("tr");
  tr.className = "log-row";
  tr.innerHTML = `
    <td class="log-time">${e.date} ${e.ts}</td>
    <td class="log-cat-cell"><span class="log-cat log-cat-${e.category.toLowerCase()}">${e.icon} ${e.category}</span></td>
    <td class="log-message">${escHtml(e.message)}</td>
    <td class="log-detail">${_fmtDetail(e.detail)}</td>`;
  tbody.prepend(tr);
}

function clearLogDisplay() {
  const tbody = $id("log-tbody");
  if (tbody)
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><span class="empty-icon">📋</span>View cleared — click Refresh to reload</div></td></tr>`;
}

async function clearLogHistory() {
  if (!confirm("ลบบันทึกระบบทั้งหมด?\nการดำเนินการนี้ไม่สามารถย้อนกลับได้"))
    return;
  try {
    const res = await fetch(`${API_BASE}/log`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
    clearLogDisplay();
    showToast("🗑 ลบบันทึกระบบเรียบร้อยแล้ว", "success");
  } catch (err) {
    showToast("❌ ลบบันทึกไม่สำเร็จ: " + err.message, "error");
  }
}

async function exportLogs() {
  try {
    showToast("📥 Exporting logs...", "info");
    const response = await fetch(`${API_BASE}/log/export`);
    const blob = await response.blob();

    // Create download link
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pytradeAI_logs_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

    showToast("✅ Logs exported successfully", "success");
  } catch (err) {
    console.error("Export failed:", err);
    showToast("❌ Failed to export logs: " + err.message, "error");
  }
}

async function exportTradeHistory() {
  try {
    showToast("📊 Exporting trade history...", "info");
    const response = await fetch(`${API_BASE}/history/export`);
    const data = await response.json();

    if (data.error) {
      showToast("⚠️ " + data.error, "warning");
      return;
    }

    // Create blob from CSV content
    const blob = new Blob([data.csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = data.filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

    showToast(`✅ Exported ${data.count} trades successfully`, "success");
  } catch (err) {
    console.error("Export failed:", err);
    showToast("❌ Failed to export history: " + err.message, "error");
  }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ═══════════════════════════════════════════════════════════
   AI Thinking Log Display
   ═══════════════════════════════════════════════════════════ */

function handleAIThinking(data) {
  // Save to memory and localStorage
  aiThinkingLog.push(data);
  if (aiThinkingLog.length > 200) {
    aiThinkingLog = aiThinkingLog.slice(-200);
  }
  storage_append_log(StorageKeys.AI_THINKING_LOG, data, 500);

  // Update UI if thinking log panel is visible
  updateAIThinkingDisplay();

  // Log to console for debugging
  console.log("🤖 AI Thinking:", data);
}

function updateAIThinkingDisplay() {
  const container = $id("ai-thinking-container");
  if (!container) return;

  const html = aiThinkingLog
    .slice(-10)
    .reverse()
    .map((entry) => {
      const ts = new Date(entry.timestamp * 1000).toLocaleTimeString();
      const stageEmoji =
        {
          market_analysis: "📊",
          performance_analysis: "📈",
          prompt_ready: "✍️",
          calling_api: "🔄",
          api_response: "📨",
          decision: "🎯",
          trade_decision: "💰",
          trade_executed: "✅",
          trade_failed: "❌",
          analysis_complete: "✔️",
        }[entry.stage] || "•";

      return `<div class="thinking-entry thinking-${entry.stage}">
      <span class="thinking-ts">${ts}</span>
      <span class="thinking-stage">${stageEmoji} ${entry.stage}</span>
      <span class="thinking-symbol">${entry.symbol}</span>
      <pre class="thinking-data">${JSON.stringify(entry.data, null, 2)}</pre>
    </div>`;
    })
    .join("");

  container.innerHTML =
    html || '<div class="empty-state">No AI thinking logs yet</div>';
}

async function loadAIThinkingLog() {
  try {
    const res = await fetch(`${API_BASE}/ai/thinking?limit=50`);
    const data = await res.json();
    aiThinkingLog = data.thinking_log || [];
    // Restore from localStorage if available
    const stored = storage_get(StorageKeys.AI_THINKING_LOG, []);
    if (stored && stored.length > aiThinkingLog.length) {
      aiThinkingLog = stored.slice(-50);
    }
    updateAIThinkingDisplay();
  } catch (err) {
    console.error("Failed to load AI thinking log:", err);
  }
}

/* ═══════════════════════════════════════════════════════════
   Trade History
   ═══════════════════════════════════════════════════════════ */

function updateTodayHistoryStats(allTrades) {
  if (!Array.isArray(allTrades)) {
    allTrades = [];
  }

  // Filter trades from today only
  const now = new Date();
  const todayStart =
    new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000;
  const todayEnd = todayStart + 86400; // 24 hours

  const todayTrades = allTrades.filter((t) => {
    // Use close_time when available (trade closed today), fallback to open time
    const tradeTime = t.close_time > 0 ? t.close_time : t.time;
    return tradeTime >= todayStart && tradeTime < todayEnd;
  });

  // Calculate today's stats
  const todayWins = todayTrades.filter((t) => t.profit > 0).length;
  const todayPnL = todayTrades.reduce((sum, t) => sum + t.profit, 0);
  const todayWinRate =
    todayTrades.length > 0
      ? Math.round((todayWins / todayTrades.length) * 100)
      : 0;

  // Update DOM
  const resultEl = $id("today-summary-result");
  if (resultEl) {
    resultEl.textContent = `${todayPnL >= 0 ? "+" : ""}$${fmt(todayPnL)}`;
    resultEl.style.color = todayPnL >= 0 ? "var(--green)" : "var(--red)";
  }

  const tradesEl = $id("today-summary-trades");
  if (tradesEl) tradesEl.textContent = todayTrades.length;

  const winrateEl = $id("today-summary-winrate");
  if (winrateEl) winrateEl.textContent = `${todayWinRate}%`;

  const winsEl = $id("today-summary-wins");
  if (winsEl) winsEl.textContent = todayWins;
}

async function loadHistory() {
  const tbody = $id("history-tbody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><span class="empty-icon">⏳</span>Loading…</div></td></tr>`;

  const days = $id("history-days")?.value || 30;
  try {
    const res = await fetch(`${API_BASE}/history?days=${days}`);
    const trades = await res.json();

    // Display today's stats first
    updateTodayHistoryStats(trades);

    const chartSection = $id("balance-chart-section");
    if (!Array.isArray(trades) || !trades.length) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><span class="empty-icon">🗂️</span>No closed trades in this period</div></td></tr>`;
      $id("history-kpis").style.display = "none";
      if (chartSection) chartSection.style.display = "none";
      return;
    }

    // Sort newest first
    trades.sort((a, b) => b.time - a.time);

    // Compute KPIs — profit > 0 is a win (same rule as dashboard)
    const wins = trades.filter((t) => t.profit > 0).length;
    const losses = trades.filter((t) => t.profit <= 0).length;
    const netPnl = trades.reduce((s, t) => s + t.profit, 0);
    const best = Math.max(...trades.map((t) => t.profit));
    const winRate = trades.length
      ? ((wins / trades.length) * 100).toFixed(1)
      : 0;

    $id("hist-total").textContent = trades.length;
    $id("hist-winrate").textContent = `${winRate}%`;
    $id("hist-wins").textContent = wins;
    $id("hist-losses").textContent = losses;
    $id("hist-pnl").textContent = `${netPnl >= 0 ? "+" : ""}$${fmt(netPnl)}`;
    $id("hist-pnl").className =
      `stat-val ${netPnl >= 0 ? "positive" : "negative"}`;
    $id("hist-best").textContent = `+$${fmt(best)}`;
    $id("history-kpis").style.display = "";
    if (chartSection) {
      chartSection.style.display = "";
      requestAnimationFrame(() => drawBalanceChart(trades));
    }

    tbody.innerHTML = trades
      .map((t) => {
        const dt = new Date(t.time * 1000);
        const dateTimeStr = dt.toLocaleString([], {
          month: "numeric",
          day: "numeric",
          year: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

        // Close time (if available)
        const closeTime = t.close_time || t.time;
        const dtClose = new Date(closeTime * 1000);
        const closeDateTimeStr = dtClose.toLocaleString([], {
          month: "numeric",
          day: "numeric",
          year: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

        const pnlClass = t.profit > 0 ? "history-pnl-pos" : "history-pnl-neg";
        const pnlStr = `${t.profit >= 0 ? "+" : ""}$${fmt(t.profit)}`;
        const typeUp = (t.type || "").toUpperCase();

        const priceOpen = t.price_open ?? t.price ?? "—";
        const priceClose = t.price_close ?? "—";

        return `
        <tr class="history-row">
          <td class="history-ticket">#${t.ticket}</td>
          <td class="history-symbol">${escHtml(t.symbol)}</td>
          <td><span class="type-badge type-badge-${typeUp.toLowerCase()}">${typeUp}</span></td>
          <td class="history-volume">${t.volume}</td>
          <td class="history-price-with-time">
            <div class="history-price">$${priceOpen}</div>
            <div class="history-time-small">${dateTimeStr}</div>
          </td>
          <td class="history-price-with-time">
            <div class="history-price">$${priceClose}</div>
            <div class="history-time-small">${closeDateTimeStr}</div>
          </td>
          <td class="${pnlClass}">${pnlStr}</td>
          <td class="history-comment">${escHtml(t.comment || "")}</td>
        </tr>`;
      })
      .join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="8" style="color:var(--red);padding:14px">Failed to load history</td></tr>`;
  }
}

function drawBalanceChart(trades) {
  const canvas = document.getElementById("balance-chart");
  if (!canvas) return;
  const sorted = [...trades].sort((a, b) => a.time - b.time);
  if (!sorted.length) return;

  let cum = 0;
  const points = [{ time: sorted[0].time, cum: 0 }];
  for (const t of sorted) {
    cum += t.profit;
    points.push({ time: t.time, cum: parseFloat(cum.toFixed(2)) });
  }

  const W = canvas.clientWidth || canvas.offsetWidth || 800;
  const H = 160;
  canvas.width = W;
  canvas.height = H;

  const ctx = canvas.getContext("2d");
  const pad = { t: 16, r: 16, b: 28, l: 58 };
  const cW = W - pad.l - pad.r,
    cH = H - pad.t - pad.b;
  const times = points.map((p) => p.time),
    cums = points.map((p) => p.cum);
  const minT = Math.min(...times),
    maxT = Math.max(...times);
  const minV = Math.min(0, ...cums),
    maxV = Math.max(0, ...cums);
  const rangeV = maxV - minV || 1,
    rangeT = maxT - minT || 1;
  const xOf = (t) => pad.l + ((t - minT) / rangeT) * cW;
  const yOf = (v) => pad.t + cH - ((v - minV) / rangeV) * cH;

  ctx.clearRect(0, 0, W, H);

  // Grid lines
  for (let i = 0; i <= 4; i++) {
    const v = minV + (rangeV * i) / 4,
      y = yOf(v);
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(W - pad.r, y);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#545d6e";
    ctx.font = "10px Inter,sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`$${v >= 0 ? "+" : ""}${v.toFixed(0)}`, pad.l - 4, y + 3);
  }

  // Zero line when axis spans both sides
  if (minV < 0 && maxV > 0) {
    const y0 = yOf(0);
    ctx.strokeStyle = "rgba(255,255,255,0.18)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.l, y0);
    ctx.lineTo(W - pad.r, y0);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  const finalVal = cums[cums.length - 1],
    isPos = finalVal >= 0;
  const lineColor = isPos ? "#22c55e" : "#ef4444";
  const grad = ctx.createLinearGradient(0, pad.t, 0, H - pad.b);
  grad.addColorStop(0, isPos ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)");
  grad.addColorStop(1, isPos ? "rgba(34,197,94,0.02)" : "rgba(239,68,68,0.02)");

  const baseY = yOf(Math.max(minV, 0));
  ctx.beginPath();
  ctx.moveTo(xOf(points[0].time), baseY);
  for (const p of points) ctx.lineTo(xOf(p.time), yOf(p.cum));
  ctx.lineTo(xOf(points[points.length - 1].time), baseY);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  points.forEach((p, i) => {
    const x = xOf(p.time),
      y = yOf(p.cum);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(
    xOf(points[points.length - 1].time),
    yOf(finalVal),
    4,
    0,
    Math.PI * 2,
  );
  ctx.fillStyle = lineColor;
  ctx.fill();
}

function updateDashboard(data) {
  // Account
  if (data.account) {
    const balFmt = `$${fmt(data.account.balance)}`;
    const eqFmt = `$${fmt(data.account.equity)}`;
    const profitFmt = `${data.account.profit >= 0 ? "+" : ""}$${fmt(
      data.account.profit,
    )}`;

    animateValue($id("account-balance"), balFmt);

    // Dashboard stat cards (equity + profit live in the cards)
    const eqEl = $id("account-equity");
    if (eqEl) eqEl.textContent = eqFmt;

    const profitEl = $id("account-profit");
    if (profitEl) {
      profitEl.textContent = profitFmt;
      profitEl.className =
        "acct-val " + (data.account.profit >= 0 ? "positive" : "negative");
    }

    // Dashboard balance stat card
    const dashBal = $id("dash-balance");
    if (dashBal) animateValue(dashBal, balFmt);
  }
  // Insights
  if (data.insights) {
    animateValue($id("win-rate"), `${data.insights.win_rate}%`);
    $id("total-trades").textContent = data.insights.total_trades;
    updateInsights(data.insights);
  }
  // Status
  if (data.status) {
    systemActive = data.status.system_active;
    updateSystemButton();
    updateMT5Badge(data.status.mt5_connected);
    updateConnectionStatus(
      data.status.mt5_connected,
      data.status.simulation_mode,
    );
  }
  // Strategies
  if (data.strategies) updateStrategies(data.strategies);
  // Positions
  if (data.positions !== undefined) updatePositions(data.positions);
  // Update today's stats
  updateTodayStats(data.positions, data.account);
  // Prices
  if (data.prices) {
    latestPrices = data.prices;
    updateTickerBar(data.prices);
  }
  // AI Auto-Trade
  if (data.ai_analysis !== undefined) updateAIAutoTab(data);
}

/* ═══════════════════════════════════════════════════════════
   Live Price Ticker Bar
   ═══════════════════════════════════════════════════════════ */

const SYMBOL_ICONS = {
  BTCUSD: "₿",
  XAUUSD: "⚜️",
  ETHUSD: "Ξ",
};

function updateTickerBar(prices) {
  const inner = $id("ticker-inner");
  if (!inner) return;

  const itemsHtml = Object.entries(prices)
    .map(([sym, p]) => {
      const icon = SYMBOL_ICONS[sym] || sym;
      const digits = sym.includes("JPY")
        ? 3
        : sym.includes("USD") &&
            !sym.startsWith("BTC") &&
            !sym.startsWith("ETH") &&
            !sym.startsWith("XAU")
          ? 5
          : 2;
      return `
            <div class="ticker-item" id="tick-${sym}">
                <span class="tick-icon">${icon}</span>
                <span class="tick-sym">${sym}</span>
                <span class="tick-bid">${p.bid.toFixed(digits)}</span>
                <span class="tick-spread">sp:${p.spread.toFixed(digits)}</span>
            </div>`;
    })
    .join("");

  // Duplicate items for seamless infinite scroll (repeat items)
  const duplicatedHtml = itemsHtml + itemsHtml;

  // Only rebuild if structure changed
  if (inner.children.length !== Object.keys(prices).length * 2) {
    inner.innerHTML = duplicatedHtml;
  } else {
    // Update prices without rebuilding HTML
    Object.entries(prices).forEach(([sym, p]) => {
      const els = document.querySelectorAll(`#tick-${sym}`);
      const digits = sym.includes("JPY")
        ? 3
        : sym.includes("USD") &&
            !sym.startsWith("BTC") &&
            !sym.startsWith("ETH") &&
            !sym.startsWith("XAU")
          ? 5
          : 2;
      els.forEach((el) => {
        const bidEl = el.querySelector(".tick-bid");
        if (bidEl) bidEl.textContent = p.bid.toFixed(digits);
      });
    });
  }
}

/* ═══════════════════════════════════════════════════════════
   Strategies Grid
   ═══════════════════════════════════════════════════════════ */

function updateStrategies(strategies) {
  // Update active strategy count stat card
  const activeCount = strategies.filter((s) => s.enabled).length;
  const dashActive = $id("dash-strategies-active");
  if (dashActive)
    dashActive.textContent = `${activeCount}/${strategies.length}`;

  // Load trading conditions for each symbol (toggle button lives inside each card)
  loadAllTradingConditions(strategies);
}

async function loadAnalytics(days = 30) {
  try {
    const res = await fetch(`${API_BASE}/analytics?days=${days}`);
    const data = await res.json();

    // Update main summary cards
    $id("analytics-net-profit-large").textContent =
      `${data.net_profit >= 0 ? "+" : ""}$${fmt(data.net_profit || 0)}`;
    $id("analytics-win-rate-large").textContent = `${data.win_rate || 0}%`;
    $id("analytics-total-trades-large").textContent = data.total_trades || 0;
    $id("analytics-drawdown-large").textContent = `$${fmt(data.drawdown || 0)}`;

    // Update detail metrics
    $id("analytics-avg-trade").textContent = `$${fmt(data.avg_profit || 0)}`;
    $id("analytics-largest-win").textContent = `$${fmt(data.largest_win || 0)}`;
    $id("analytics-largest-loss").textContent =
      `$${fmt(data.largest_loss || 0)}`;
    $id("analytics-total-profit").textContent =
      `$${fmt(data.total_profit || 0)}`;

    // Store latest analytics data for export
    window.latestAnalyticsData = data;

    // Update By Symbol table
    const symbolTbody = $id("analytics-by-symbol");
    if (data.by_symbol && Object.keys(data.by_symbol).length > 0) {
      symbolTbody.innerHTML = Object.entries(data.by_symbol)
        .map(
          ([sym, stats]) => `
        <tr>
          <td><strong>${sym}</strong></td>
          <td>${stats.trades}</td>
          <td>${stats.wins}</td>
          <td>${stats.win_rate || 0}%</td>
          <td class="${stats.profit >= 0 ? "positive" : "negative"}">$${fmt(stats.profit)}</td>
        </tr>
      `,
        )
        .join("");
    } else {
      symbolTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">ไม่มีข้อมูล</td></tr>`;
    }

    // Update By Strategy table
    const strategyTbody = $id("analytics-by-strategy");
    if (data.by_strategy && Object.keys(data.by_strategy).length > 0) {
      strategyTbody.innerHTML = Object.entries(data.by_strategy)
        .map(
          ([strat, stats]) => `
        <tr>
          <td><strong>${escHtml(strat)}</strong></td>
          <td>${stats.trades}</td>
          <td>${stats.wins}</td>
          <td>${stats.win_rate || 0}%</td>
          <td class="${stats.profit >= 0 ? "positive" : "negative"}">$${fmt(stats.profit)}</td>
        </tr>
      `,
        )
        .join("");
    } else {
      strategyTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">ไม่มีข้อมูล</td></tr>`;
    }

    // Draw Daily P&L chart if canvas exists
    if (
      data.daily_pnl &&
      Array.isArray(data.daily_pnl) &&
      data.daily_pnl.length > 0
    ) {
      drawDailyPnLChart(data.daily_pnl);
    }

    // Draw Win/Loss pie chart
    drawWinLossPieChart(
      data.total_trades || 0,
      data.total_trades
        ? Math.round((data.win_rate / 100) * data.total_trades)
        : 0,
    );

    // Populate individual trades table
    const tradesTbody = $id("analytics-trades-tbody");
    if (data.trades && Array.isArray(data.trades) && data.trades.length > 0) {
      // Sort trades by time, newest first
      const sortedTrades = [...data.trades].sort(
        (a, b) => (b.time || 0) - (a.time || 0),
      );

      tradesTbody.innerHTML = sortedTrades
        .map((t) => {
          const pnlClass = t.profit > 0 ? "positive" : "negative";
          const pnlStr = `${t.profit >= 0 ? "+" : ""}$${fmt(t.profit || 0)}`;
          const typeUp = (t.type || "").toUpperCase();
          const priceOpen = t.price_open ?? t.price ?? "—";

          return `
          <tr>
            <td>#${t.ticket || "—"}</td>
            <td>${escHtml(t.symbol || "—")}</td>
            <td><span class="type-badge type-badge-${typeUp.toLowerCase()}">${typeUp}</span></td>
            <td>$${priceOpen}</td>
            <td class="${pnlClass}">${pnlStr}</td>
          </tr>`;
        })
        .join("");
    } else {
      tradesTbody.innerHTML = `<tr><td colspan="5" style="text-align:center">ไม่มีข้อมูล</td></tr>`;
    }
  } catch (err) {
    console.error("Failed to load analytics:", err);
  }
}

async function loadAnalyticsWithDateRange() {
  const days = parseInt($id("analytics-start-date")?.value || 30);
  await loadAnalytics(days);
}

function exportAnalyticsCSV() {
  if (!window.latestAnalyticsData) {
    alert("No analytics data to export. Please load analytics first.");
    return;
  }

  const data = window.latestAnalyticsData;
  const lines = [];

  // Header
  lines.push("pytradeAI - Performance Analytics Report");
  lines.push(`Generated: ${new Date().toLocaleString()}`);
  lines.push("");

  // Summary
  lines.push("SUMMARY STATISTICS");
  lines.push(`Total Trades,${data.total_trades || 0}`);
  lines.push(`Win Rate,${data.win_rate || 0}%`);
  lines.push(`Net Profit,$${fmt(data.net_profit || 0)}`);
  lines.push(`Total Profit,$${fmt(data.total_profit || 0)}`);
  lines.push(`Total Loss,$${fmt(data.total_loss || 0)}`);
  lines.push(`Average Trade,$${fmt(data.avg_profit || 0)}`);
  lines.push(`Largest Win,$${fmt(data.largest_win || 0)}`);
  lines.push(`Largest Loss,$${fmt(data.largest_loss || 0)}`);
  lines.push(`Drawdown,$${fmt(data.drawdown || 0)}`);
  lines.push("");

  // By Symbol
  lines.push("PERFORMANCE BY SYMBOL");
  lines.push("Symbol,Trades,Wins,Win Rate %,P&L");
  if (data.by_symbol) {
    Object.entries(data.by_symbol).forEach(([sym, stats]) => {
      lines.push(
        `${sym},${stats.trades},${stats.wins},${stats.win_rate || 0},${fmt(stats.profit)}`,
      );
    });
  }
  lines.push("");

  // By Strategy
  lines.push("PERFORMANCE BY STRATEGY");
  lines.push("Strategy,Trades,Wins,Win Rate %,P&L");
  if (data.by_strategy) {
    Object.entries(data.by_strategy).forEach(([strat, stats]) => {
      lines.push(
        `"${strat}",${stats.trades},${stats.wins},${stats.win_rate || 0},${fmt(stats.profit)}`,
      );
    });
  }
  lines.push("");

  // Daily P&L
  if (data.daily_pnl && Array.isArray(data.daily_pnl)) {
    lines.push("DAILY P&L");
    lines.push("Date,P&L");
    data.daily_pnl.forEach((item) => {
      lines.push(`${item.date},${fmt(item.profit)}`);
    });
  }

  // Download CSV
  const csv = lines.join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `analytics-${new Date().getTime()}.csv`;
  link.click();
}

function drawDailyPnLChart(dailyPnL) {
  const canvas = $id("chart-daily-pnl");
  if (!canvas) return;

  const W = canvas.clientWidth || 400;
  const H = 150;
  canvas.width = W;
  canvas.height = H;

  const ctx = canvas.getContext("2d");
  const pad = { t: 10, r: 10, b: 20, l: 50 };
  const cW = W - pad.l - pad.r;
  const cH = H - pad.t - pad.b;

  const pnlValues = dailyPnL.map((d) => d.profit);
  const minV = Math.min(0, ...pnlValues);
  const maxV = Math.max(0, ...pnlValues);
  const rangeV = maxV - minV || 1;

  const barW = Math.max(1, cW / dailyPnL.length - 2);
  const yOf = (v) => pad.t + cH - ((v - minV) / rangeV) * cH;
  const zeroY = yOf(0);

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "rgba(100, 100, 100, 0.1)";
  ctx.fillRect(pad.l, pad.t, cW, cH);

  // Draw zero line
  ctx.strokeStyle = "rgba(128, 128, 128, 0.3)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.l, zeroY);
  ctx.lineTo(pad.l + cW, zeroY);
  ctx.stroke();

  // Draw bars
  dailyPnL.forEach((item, i) => {
    const x = pad.l + (i / dailyPnL.length) * cW + 1;
    const y = yOf(item.profit);
    const h = Math.abs(zeroY - y);
    ctx.fillStyle =
      item.profit >= 0 ? "rgba(76, 175, 80, 0.7)" : "rgba(244, 67, 54, 0.7)";
    ctx.fillRect(x, Math.min(y, zeroY), barW - 2, h);
  });
}

function drawWinLossPieChart(totalTrades, wins) {
  const canvas = $id("chart-win-loss-pie");
  if (!canvas) return;

  const W = 200;
  const H = 150;
  canvas.width = W;
  canvas.height = H;

  const ctx = canvas.getContext("2d");
  const cx = W / 2;
  const cy = H / 2;
  const radius = 50;

  const losses = totalTrades - wins;
  const winPercent = totalTrades > 0 ? wins / totalTrades : 0;

  ctx.clearRect(0, 0, W, H);

  // Win slice (green)
  ctx.fillStyle = "rgba(76, 175, 80, 0.8)";
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.arc(
    cx,
    cy,
    radius,
    -Math.PI / 2,
    -Math.PI / 2 + 2 * Math.PI * winPercent,
  );
  ctx.lineTo(cx, cy);
  ctx.fill();

  // Loss slice (red)
  ctx.fillStyle = "rgba(244, 67, 54, 0.8)";
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.arc(
    cx,
    cy,
    radius,
    -Math.PI / 2 + 2 * Math.PI * winPercent,
    (3 * Math.PI) / 2,
  );
  ctx.lineTo(cx, cy);
  ctx.fill();

  // Labels
  ctx.fillStyle = "white";
  ctx.font = "bold 12px Arial";
  ctx.textAlign = "center";
  ctx.fillText(`${(winPercent * 100).toFixed(1)}%`, cx - 30, cy);
  ctx.fillText(`${((1 - winPercent) * 100).toFixed(1)}%`, cx + 30, cy);
}

function drawPerformanceHeatmap(bySymbol) {
  const canvas = $id("chart-heatmap");
  if (!canvas) return;

  const W = canvas.clientWidth || 800;
  const H = 200;
  canvas.width = W;
  canvas.height = H;

  const ctx = canvas.getContext("2d");
  const symbols = Object.keys(bySymbol).sort();
  const hours = Array.from({ length: 24 }, (_, i) => i);

  if (symbols.length === 0) return;

  const cellW = (W - 100) / 24;
  const cellH = (H - 30) / symbols.length;

  ctx.clearRect(0, 0, W, H);

  // Draw heatmap cells
  symbols.forEach((sym, symIdx) => {
    const stats = bySymbol[sym];
    const avgWinRate = stats.win_rate || 0;

    hours.forEach((hour) => {
      // Simulate data by varying the win rate based on hour
      const timeOfDay = Math.sin((hour / 24) * Math.PI) * 0.3 + 0.5;
      const cellValue = Math.min(
        100,
        Math.max(0, avgWinRate * timeOfDay * 1.5),
      );

      // Color gradient: red (0%) -> yellow (50%) -> green (100%)
      let color;
      if (cellValue < 50) {
        const ratio = cellValue / 50;
        const r = Math.floor(255);
        const g = Math.floor(255 * ratio);
        color = `rgb(${r}, ${g}, 0)`;
      } else {
        const ratio = (cellValue - 50) / 50;
        const r = Math.floor(255 * (1 - ratio));
        const g = 255;
        color = `rgb(${r}, ${g}, 0)`;
      }

      const x = 100 + hour * cellW;
      const y = symIdx * cellH;

      ctx.fillStyle = color;
      ctx.fillRect(x, y, cellW - 1, cellH - 1);

      // Border
      ctx.strokeStyle = "rgba(50, 50, 50, 0.2)";
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x, y, cellW - 1, cellH - 1);
    });
  });

  // Y-axis labels (symbols)
  ctx.fillStyle = "var(--text-normal)";
  ctx.font = "11px Arial";
  ctx.textAlign = "right";
  symbols.forEach((sym, idx) => {
    ctx.fillText(sym, 95, idx * cellH + cellH / 2 + 4);
  });

  // X-axis labels (hours)
  ctx.fillStyle = "var(--text-muted)";
  ctx.textAlign = "center";
  for (let h = 0; h < 24; h += 4) {
    ctx.fillText(h + ":00", 100 + h * cellW + cellW / 2, H - 8);
  }
}

function drawStrategyComparison(byStrategy) {
  const strategies = Object.entries(byStrategy);
  if (strategies.length === 0) return;

  // Find best/worst/average
  const profitValues = strategies.map(([_, stats]) => stats.profit);
  const winRates = strategies.map(([_, stats]) => stats.win_rate);

  const bestStrat = strategies.reduce((a, b) =>
    a[1].profit > b[1].profit ? a : b,
  );
  const worstStrat = strategies.reduce((a, b) =>
    a[1].profit < b[1].profit ? a : b,
  );
  const avgProfit = profitValues.reduce((a, b) => a + b, 0) / strategies.length;
  const avgWinRate = winRates.reduce((a, b) => a + b, 0) / strategies.length;

  const tbody = $id("analytics-comparison-tbody");
  const header = $id("comp-best-strategy");

  if (header) {
    header.textContent = bestStrat[0];
  }

  // Build comparison rows
  const rows = [
    {
      metric: "P&L (Total)",
      best: `$${fmt(bestStrat[1].profit)}`,
      avg: `$${fmt(avgProfit)}`,
      worst: `$${fmt(worstStrat[1].profit)}`,
    },
    {
      metric: "Win Rate %",
      best: `${(bestStrat[1].win_rate || 0).toFixed(1)}%`,
      avg: `${avgWinRate.toFixed(1)}%`,
      worst: `${(worstStrat[1].win_rate || 0).toFixed(1)}%`,
    },
    {
      metric: "Trades Count",
      best: bestStrat[1].trades,
      avg: Math.round(
        strategies.reduce((s, [_, st]) => s + st.trades, 0) / strategies.length,
      ),
      worst: worstStrat[1].trades,
    },
    {
      metric: "Wins",
      best: bestStrat[1].wins,
      avg: Math.round(
        strategies.reduce((s, [_, st]) => s + st.wins, 0) / strategies.length,
      ),
      worst: worstStrat[1].wins,
    },
  ];

  tbody.innerHTML = rows
    .map(
      (row) => `
    <tr>
      <td><strong>${row.metric}</strong></td>
      <td style="color: var(--green); font-weight: 600;">${row.best}</td>
      <td style="color: var(--text-normal);">${row.avg}</td>
      <td style="color: var(--red);">${row.worst}</td>
    </tr>
  `,
    )
    .join("");
}

async function loadAllTradingConditions(strategies) {
  const container = $id("trading-conditions");
  if (!container) return;

  // Build a map of enabled state per symbol
  const enabledMap = Object.fromEntries(
    strategies.map((s) => [s.symbol, s.enabled]),
  );

  try {
    const promises = strategies.map((s) =>
      fetch(`${API_BASE}/strategies/${s.symbol}/conditions`)
        .then((r) => r.json())
        .catch((e) => ({
          symbol: s.symbol,
          status: "error",
          error: e.message,
        })),
    );

    const conditions = await Promise.all(promises);
    container.innerHTML = conditions
      .map((c) => _buildConditionCard(c, enabledMap[c.symbol] ?? false))
      .join("");
  } catch (err) {
    console.error("Failed to load trading conditions:", err);
  }
}

function _buildConditionCard(cond, enabled = false) {
  const toggleBtn = `<button class="tc-toggle ${enabled ? "on" : ""}" onclick="toggleStrategy('${cond.symbol}')" title="${enabled ? "ปิดกลยุทธ์" : "เปิดกลยุทธ์"} ${cond.symbol}">${enabled ? "ON" : "OFF"}</button>`;

  if (cond.status !== "ready") {
    return `
      <div class="trading-condition-card">
        <div class="tc-header">
          <span class="tc-symbol">${cond.symbol}</span>
          ${toggleBtn}
        </div>
        <div style="font-size:11px; color:var(--text-muted)">⚠️ ${cond.message || "No data"}</div>
      </div>`;
  }

  const indicators = cond.technical_indicators;
  const buy = cond.buy_signal;
  const sell = cond.sell_signal;
  const buyTriggered = buy.triggered ? "buy" : "neutral";
  const sellTriggered = sell.triggered ? "sell" : "neutral";
  const uid = `tc-spark-${cond.symbol}`;

  const html = `
    <div class="trading-condition-card">
      <div class="tc-header">
        <span class="tc-symbol">${cond.symbol}</span>
        <span class="tc-price">$${cond.current_price}</span>
        ${toggleBtn}
      </div>

      <canvas id="${uid}" class="tc-sparkline" width="220" height="52"></canvas>

      <div class="tc-indicators">
        <div class="tc-ind-item">
          <div class="tc-ind-label">RSI-14</div>
          <div class="tc-ind-value ${indicators.rsi_14 < 35 ? "tc-val-bull" : indicators.rsi_14 > 65 ? "tc-val-bear" : ""}">${indicators.rsi_14.toFixed(1)}</div>
        </div>
        <div class="tc-ind-item">
          <div class="tc-ind-label">ADX-14</div>
          <div class="tc-ind-value ${indicators.adx_14 >= 20 ? "tc-val-bull" : "tc-val-bear"}">${(indicators.adx_14 || 0).toFixed(1)}${indicators.adx_trending === false ? " ⚠️" : ""}</div>
        </div>
        <div class="tc-ind-item">
          <div class="tc-ind-label">MA ${indicators.ma_fast_period || 7} / ${indicators.ma_slow_period || 20}</div>
          <div class="tc-ind-value">${indicators.ma_7.toFixed(5)} / ${indicators.ma_20.toFixed(5)}</div>
        </div>
        <div class="tc-ind-item">
          <div class="tc-ind-label">BB ${indicators.bb_sigma || 2.0}σ Upper</div>
          <div class="tc-ind-value">${indicators.bb_upper.toFixed(5)}</div>
        </div>
        <div class="tc-ind-item">
          <div class="tc-ind-label">BB ${indicators.bb_sigma || 2.0}σ Lower</div>
          <div class="tc-ind-value">${indicators.bb_lower.toFixed(5)}</div>
        </div>
      </div>

      <div class="tc-signals">
        <div class="tc-signal-box ${buyTriggered}">
          🟢 BUY (${buy.score})
        </div>
        <div class="tc-signal-box ${sellTriggered}">
          🔴 SELL (${sell.score})
        </div>
      </div>

      <div class="tc-conditions">
        <strong style="color:var(--green)">Buy:</strong>
        ${buy.conditions.map((c) => `<div>${c}</div>`).join("")}
        <strong style="color:var(--red); margin-top:4px; display:block">Sell:</strong>
        ${sell.conditions.map((c) => `<div>${c}</div>`).join("")}
      </div>
    </div>`;

  // Draw sparkline after DOM insert (deferred)
  requestAnimationFrame(() => {
    _drawSparkline(uid, cond.price_history || [], {
      bbUpper: cond.bb_upper,
      bbLower: cond.bb_lower,
      maFast: cond.ma_fast,
      isBuy: buy.triggered,
      isSell: sell.triggered,
    });
  });

  return html;
}

function _drawSparkline(
  canvasId,
  prices,
  { bbUpper, bbLower, maFast, isBuy, isSell } = {},
) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !prices || prices.length < 2) return;

  const W = canvas.offsetWidth || canvas.width;
  const H = canvas.height;
  canvas.width = W;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);

  const pad = { l: 0, r: 0, t: 4, b: 4 };
  const cW = W - pad.l - pad.r;
  const cH = H - pad.t - pad.b;

  // Price range — include BB bands if available
  const allVals = [...prices];
  if (bbUpper) allVals.push(bbUpper);
  if (bbLower) allVals.push(bbLower);
  const minP = Math.min(...allVals);
  const maxP = Math.max(...allVals);
  const range = maxP - minP || 1;

  const xOf = (i) => pad.l + (i / (prices.length - 1)) * cW;
  const yOf = (v) => pad.t + cH - ((v - minP) / range) * cH;

  // BB channel fill
  if (bbUpper && bbLower) {
    ctx.beginPath();
    ctx.moveTo(pad.l, yOf(bbUpper));
    ctx.lineTo(W - pad.r, yOf(bbUpper));
    ctx.lineTo(W - pad.r, yOf(bbLower));
    ctx.lineTo(pad.l, yOf(bbLower));
    ctx.closePath();
    ctx.fillStyle = "rgba(99,179,237,0.07)";
    ctx.fill();

    // BB upper/lower lines (dashed)
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = "rgba(99,179,237,0.35)";
    ctx.lineWidth = 1;
    [bbUpper, bbLower].forEach((v) => {
      ctx.beginPath();
      ctx.moveTo(pad.l, yOf(v));
      ctx.lineTo(W - pad.r, yOf(v));
      ctx.stroke();
    });
    ctx.setLineDash([]);
  }

  // MA fast line
  if (maFast) {
    const maY = yOf(maFast);
    ctx.beginPath();
    ctx.moveTo(pad.l, maY);
    ctx.lineTo(W - pad.r, maY);
    ctx.strokeStyle = "rgba(251,191,36,0.5)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Price line gradient
  const lineColor = isBuy ? "#22c55e" : isSell ? "#ef4444" : "#64748b";
  const grad = ctx.createLinearGradient(0, pad.t, 0, H);
  grad.addColorStop(
    0,
    isBuy
      ? "rgba(34,197,94,0.18)"
      : isSell
        ? "rgba(239,68,68,0.18)"
        : "rgba(100,116,139,0.10)",
  );
  grad.addColorStop(1, "rgba(0,0,0,0)");

  // Fill area under price line
  ctx.beginPath();
  ctx.moveTo(xOf(0), yOf(prices[0]));
  prices.forEach((p, i) => ctx.lineTo(xOf(i), yOf(p)));
  ctx.lineTo(xOf(prices.length - 1), H);
  ctx.lineTo(xOf(0), H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Price line
  ctx.beginPath();
  ctx.moveTo(xOf(0), yOf(prices[0]));
  prices.forEach((p, i) => ctx.lineTo(xOf(i), yOf(p)));
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = "round";
  ctx.stroke();

  // Current price dot
  const lastX = xOf(prices.length - 1);
  const lastY = yOf(prices[prices.length - 1]);
  ctx.beginPath();
  ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = lineColor;
  ctx.fill();
}

/* ═══════════════════════════════════════════════════════════
   Insights
   ═══════════════════════════════════════════════════════════ */

function updateInsights(ins) {
  $id("most-lost-symbol").textContent = ins.most_lost_symbol?.symbol || "None!";
  $id("weakest-action").textContent = ins.weakest_action?.action || "Perfect";
  $id("total-loss-impact").textContent = `$${fmt(ins.total_loss_impact || 0)}`;

  const wk = $id("weakest-action");
  wk.style.color =
    wk.textContent === "Perfect" ? "var(--green)" : "var(--yellow)";
}

/* ═══════════════════════════════════════════════════════════
   Today's Summary Tracking
   ═══════════════════════════════════════════════════════════ */

function getTodayTrades() {
  const today = new Date().toDateString();
  let allTrades = storage_get(StorageKeys.TODAY_TRADES, {});

  // Clean old dates
  const dates = Object.keys(allTrades);
  dates.forEach((d) => {
    if (d !== today) delete allTrades[d];
  });

  if (!allTrades[today]) {
    allTrades[today] = { trades: [], startBalance: 0, startTime: Date.now() };
  }

  return (
    allTrades[today] || { trades: [], startBalance: 0, startTime: Date.now() }
  );
}

function saveTodayTrades(trades) {
  const today = new Date().toDateString();
  let allTrades = storage_get(StorageKeys.TODAY_TRADES, {});
  allTrades[today] = trades;
  storage_set(StorageKeys.TODAY_TRADES, allTrades);
}

function recordTradeAsToday(tradeResult) {
  if (!tradeResult || !tradeResult.success) return;

  const today = getTodayTrades();
  today.trades.push({
    symbol: tradeResult.symbol,
    type: tradeResult.type,
    ticket: tradeResult.ticket,
    time: Date.now(),
    result: "pending", // will be updated when closed
  });
  saveTodayTrades(today);
}

async function updateTodayStats(positions, account) {
  // Fetch today's closed trades from API and calculate stats
  try {
    const res = await fetch(`${API_BASE}/history?days=1`);
    let allTrades = await res.json();

    if (!Array.isArray(allTrades)) {
      allTrades = [];
    }

    // Filter trades from today only
    const now = new Date();
    const todayStart =
      new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() /
      1000;
    const todayEnd = todayStart + 86400; // 24 hours

    const todayTrades = allTrades.filter((t) => {
      // Use close_time when available (trade closed today), fallback to open time
      const tradeTime = t.close_time > 0 ? t.close_time : t.time;
      return tradeTime >= todayStart && tradeTime < todayEnd;
    });

    // Calculate today's stats
    const todayWins = todayTrades.filter((t) => t.profit > 0).length;
    const todayPnL = todayTrades.reduce((sum, t) => sum + t.profit, 0);
    const todayWinRate =
      todayTrades.length > 0
        ? Math.round((todayWins / todayTrades.length) * 100)
        : 0;

    // Update DOM — closed trades only, consistent with History page
    const resultEl = $id("today-result");
    if (resultEl) {
      resultEl.textContent = `${todayPnL >= 0 ? "+" : ""}$${fmt(todayPnL)}`;
      resultEl.style.color = todayPnL >= 0 ? "var(--green)" : "var(--red)";
    }

    const tradesEl = $id("today-trades");
    if (tradesEl) tradesEl.textContent = todayTrades.length;

    const winrateEl = $id("today-winrate");
    if (winrateEl) winrateEl.textContent = todayWinRate;
  } catch (err) {
    console.error("Failed to update today stats:", err);
    // Fallback: show — for error state
    const resultEl = $id("today-result");
    if (resultEl) {
      resultEl.textContent = "—";
      resultEl.style.color = "var(--text-muted)";
    }
  }
}

/* ═══════════════════════════════════════════════════════════
   Positions Table
   ═══════════════════════════════════════════════════════════ */

function getPipValue(symbol) {
  // Try to get pip value from MT5 backend first
  if (pipValues[symbol] !== undefined) {
    return pipValues[symbol];
  }
  // Fallback to hardcoded defaults (in case API hasn't loaded yet)
  const defaults = {
    BTCUSD: 0.1,
    XAUUSD: 0.01,
    ETHUSD: 0.1,
  };
  return defaults[symbol] || 0.1;
}

function calculatePips(symbol, priceOpen, priceCurrent, type) {
  const pipValue = getPipValue(symbol);
  const priceDiff = priceCurrent - priceOpen;
  const pips = type === "BUY" ? priceDiff / pipValue : -priceDiff / pipValue;
  return Math.round(pips);
}

// ─── Default TP/SL Values by Symbol (Dollar Pips: 1 pip = $0.01) ──
// e.g. 400 pips = $4.00 target profit at any symbol/lot combination
function getDefaultTPPips(symbol) {
  const defaults = {
    BTCUSD: 400, // $4.00 target
    XAUUSD: 200, // $2.00 target
    ETHUSD: 400, // $4.00 target
  };
  return defaults[symbol] || 200;
}

function getDefaultSLPips(symbol) {
  const defaults = {
    BTCUSD: 200, // $2.00 risk
    XAUUSD: 100, // $1.00 risk
    ETHUSD: 200, // $2.00 risk
  };
  return defaults[symbol] || 100;
}

function updatePositions(positions) {
  window._lastPositions = positions; // cache for Force toggle re-render
  const tbody = $id("positions-body");
  const noPos = $id("no-positions");
  const tbodyDash = $id("positions-body-dash");
  const noPosDash = $id("no-positions-dash");

  // Update open position count stat
  const posCount = $id("dash-pos-count");
  if (posCount) posCount.textContent = positions ? positions.length : 0;

  if (!positions || positions.length === 0) {
    if (tbody) tbody.innerHTML = "";
    if (noPos) noPos.style.display = "";
    if (tbodyDash) tbodyDash.innerHTML = "";
    if (noPosDash) noPosDash.style.display = "";
    return;
  }

  if (noPos) noPos.style.display = "none";
  if (noPosDash) noPosDash.style.display = "none";

  const fullRows = positions
    .map((p) => {
      const tc = p.type === "BUY" ? "pos-buy" : "pos-sell";
      const pc = p.profit >= 0 ? "pos-pos" : "pos-neg";
      const sign = p.profit >= 0 ? "+" : "";

      // Calculate pips from current price
      const pips = calculatePips(
        p.symbol,
        p.price_open,
        p.price_current,
        p.type,
      );
      const pipsClass = pips >= 0 ? "pos-pos" : "pos-neg";

      // Calculate pips to SL and TP — measured from open price
      const pipValue = getPipValue(p.symbol);
      const slPips = p.sl ? Math.round((p.sl - p.price_open) / pipValue) : null;
      const tpPips = p.tp ? Math.round((p.tp - p.price_open) / pipValue) : null;

      // For SELL positions, swap SL and TP display order
      const slCell = p.sl
        ? `${p.sl.toFixed(5)}<br><span style="color:var(--text-secondary);">(${slPips > 0 ? "+" : ""}${slPips} p)</span>`
        : "—";
      const tpCell = p.tp
        ? `${p.tp.toFixed(5)}<br><span style="color:var(--text-secondary);">(${tpPips > 0 ? "+" : ""}${tpPips} p)</span>`
        : "—";
      const [firstCell, secondCell] =
        p.type === "SELL" ? [tpCell, slCell] : [slCell, tpCell];

      return `
        <tr>
            <td class="pos-sym">${p.symbol}</td>
            <td class="${tc}">${p.type}</td>
            <td>${p.volume}</td>
            <td>${p.price_open}</td>
            <td>${p.price_current}</td>
            <td class="${pipsClass}" style="font-size:0.9rem; font-weight:600;">${sign}${pips} pips</td>
            <td style="font-size:10px;">${firstCell}</td>
            <td style="font-size:10px;">${secondCell}</td>
            <td><span class="pos-pnl ${p.profit >= 0 ? "profit" : "loss"}">${sign}$${p.profit.toFixed(2)}</span></td>
            <td>
              <button class="btn-close-pos" onclick="closePosition(${p.ticket})">Close</button>
              ${forceCloseEnabled ? `<button class="btn-force-pos" onclick="closePosition(${p.ticket}, true)" title="Force close — bypass strategy exit signal">⚡ Force</button>` : ""}
            </td>
        </tr>`;
    })
    .join("");
  if (tbody) tbody.innerHTML = fullRows;

  // Dashboard preview with detailed pips
  const dashRows = positions
    .map((p) => {
      const tc = p.type === "BUY" ? "pos-buy" : "pos-sell";
      const pc = p.profit >= 0 ? "pos-pos" : "pos-neg";
      const sign = p.profit >= 0 ? "+" : "";

      // Calculate pips from current price
      const pips = calculatePips(
        p.symbol,
        p.price_open,
        p.price_current,
        p.type,
      );
      const pipsClass = pips >= 0 ? "pos-pos" : "pos-neg";

      // Calculate pips to SL and TP — measured from open price
      const pipValue = getPipValue(p.symbol);
      const slPips = p.sl ? Math.round((p.sl - p.price_open) / pipValue) : null;
      const tpPips = p.tp ? Math.round((p.tp - p.price_open) / pipValue) : null;

      // For SELL positions, swap SL and TP display order
      const slCell = p.sl
        ? `${p.sl.toFixed(5)}<br><span style="color:var(--text-secondary); font-size:9px;">(${slPips > 0 ? "+" : ""}${slPips} p)</span>`
        : "—";
      const tpCell = p.tp
        ? `${p.tp.toFixed(5)}<br><span style="color:var(--text-secondary); font-size:9px;">(${tpPips > 0 ? "+" : ""}${tpPips} p)</span>`
        : "—";
      const [firstCell, secondCell] =
        p.type === "SELL" ? [tpCell, slCell] : [slCell, tpCell];

      return `
        <tr>
            <td class="pos-sym">${p.symbol}</td>
            <td class="${tc}">${p.type}</td>
            <td>${p.volume}</td>
            <td>${p.price_open}</td>
            <td>${p.price_current}</td>
            <td class="${pipsClass}" style="font-size:0.9rem; font-weight:600;">${sign}${pips} pips</td>
            <td style="font-size:10px;">${firstCell}</td>
            <td style="font-size:10px;">${secondCell}</td>
            <td><span class="pos-pnl ${p.profit >= 0 ? "profit" : "loss"}">${sign}$${p.profit.toFixed(2)}</span></td>
            <td>
              <button class="btn-close-pos" onclick="closePosition(${p.ticket})">Close</button>
              ${forceCloseEnabled ? `<button class="btn-force-pos" onclick="closePosition(${p.ticket}, true)" title="Force close — bypass strategy exit signal">⚡ Force</button>` : ""}
            </td>
        </tr>`;
    })
    .join("");
  if (tbodyDash) tbodyDash.innerHTML = dashRows;
}

/* ═══════════════════════════════════════════════════════════
   MT5 Connection Panel
   ═══════════════════════════════════════════════════════════ */

function openMT5Panel() {
  $id("mt5-modal").classList.add("show");
  loadSavedAccounts();
}
function closeMT5Panel(e) {
  // Block close when login is required (no connection yet)
  if (_loginRequired) return;
  if (!e || e.target === $id("mt5-modal"))
    $id("mt5-modal").classList.remove("show");
}
function openMT5LoginPrompt() {
  _loginRequired = true;
  const modal = $id("mt5-modal");
  if (modal) modal.classList.add("show", "login-required");
  const notice = $id("mt5-login-notice");
  if (notice) notice.style.display = "";
  switchMT5Tab("connect");
}

// ─── Saved Accounts ──────────────────────────────────────────

async function loadSavedAccounts() {
  try {
    const res = await fetch(`${API_BASE}/mt5/saved-accounts`);
    const accounts = await res.json();
    renderSavedAccounts(accounts);
  } catch {
    renderSavedAccounts([]);
  }
}

function renderSavedAccounts(accounts) {
  const list = $id("saved-accounts-list");
  const count = $id("saved-accounts-count");
  count.textContent = `${accounts.length} account${
    accounts.length !== 1 ? "s" : ""
  }`;

  if (!accounts.length) {
    list.innerHTML = '<div class="saved-empty">No saved accounts yet</div>';
    return;
  }

  list.innerHTML = accounts
    .map(
      (a) => `
        <div class="saved-account-item ${
          a.auto_connect ? "is-default" : ""
        }" id="sa-${encodeURIComponent(a.name)}">
            <div class="sa-info" onclick="fillAccountForm(${a.login}, '${escJs(
              a.server,
            )}', '${escJs(a.name)}', ${a.auto_connect})">
                <span class="sa-name">${escHtml(a.name)}</span>
                <span class="sa-detail">${a.login || "—"} · ${escHtml(
                  a.server || "Simulation",
                )}</span>
                ${
                  a.auto_connect
                    ? '<span class="sa-default-badge">★ Default</span>'
                    : ""
                }
            </div>
            <div class="sa-actions">
                <button class="sa-btn sa-btn-connect"
                        onclick="quickConnect(${a.login}, '${escJs(
                          a.server,
                        )}', '${escJs(a.name)}')"
                        title="Connect">🔗</button>
                <button class="sa-btn sa-btn-default ${
                  a.auto_connect ? "active" : ""
                }"
                        onclick="setDefaultAccount('${escJs(a.name)}')"
                        title="${
                          a.auto_connect ? "Remove default" : "Set as default"
                        }">★</button>
                <button class="sa-btn sa-btn-delete"
                        onclick="deleteSavedAccount('${escJs(a.name)}')"
                        title="Delete">🗑</button>
            </div>
        </div>`,
    )
    .join("");
}

function fillAccountForm(login, server, name, autoConnect) {
  $id("mt5-login").value = login || "";
  $id("mt5-server").value = server || "";
  $id("mt5-name").value = name || "";
  $id("mt5-auto-connect").checked = !!autoConnect;
  // password is never sent back — user re-enters if needed
  $id("mt5-password").value = "";
  $id("mt5-password").placeholder = "(re-enter to update)";
}

async function quickConnect(login, server, name) {
  // Fill form then trigger connect — password prompt if missing
  fillAccountForm(login, server, name, false);
  // password lives only on the server — call connect via API directly
  const res = await fetch(`${API_BASE}/mt5/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login, password: "__use_saved__", server }),
  });
  const data = await res.json();
  if (!res.ok) {
    // password not cached — let user fill it in
    showToast("⚠️ Re-enter password to connect", "info");
    return;
  }
  updateConnectionStatus(data.connected, data.simulation_mode);
  showToast(
    data.simulation_mode
      ? "🔌 Connected (Simulation)"
      : `✅ Connected: ${name}`,
    "success",
  );
  closeMT5Panel();
}

async function doSaveAccount() {
  const name = ($id("mt5-name").value || "").trim();
  const login = parseInt($id("mt5-login").value) || 0;
  const password = $id("mt5-password").value || "";
  const server = $id("mt5-server").value || "";
  const autoConnect = $id("mt5-auto-connect").checked;

  if (!name) {
    showToast("⚠️ Enter an Account Name to save", "error");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/mt5/save-account`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        login,
        password,
        server,
        auto_connect: autoConnect,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Save failed");

    showToast(
      `💾 Saved: "${name}"${autoConnect ? " (set as default)" : ""}`,
      "success",
    );
    loadSavedAccounts();
  } catch (err) {
    showToast(`❌ ${err.message}`, "error");
  }
}

async function deleteSavedAccount(name) {
  if (!confirm(`Delete saved account "${name}"?`)) return;
  try {
    const res = await fetch(
      `${API_BASE}/mt5/saved-accounts/${encodeURIComponent(name)}`,
      {
        method: "DELETE",
      },
    );
    if (!res.ok) throw new Error("Delete failed");
    showToast(`🗑 Deleted: "${name}"`, "info");
    loadSavedAccounts();
  } catch (err) {
    showToast(`❌ ${err.message}`, "error");
  }
}

async function setDefaultAccount(name) {
  try {
    const res = await fetch(
      `${API_BASE}/mt5/set-default/${encodeURIComponent(name)}`,
      {
        method: "POST",
      },
    );
    if (!res.ok) throw new Error("Failed");
    showToast(`★ Default set: "${name}"`, "success");
    loadSavedAccounts();
  } catch (err) {
    showToast(`❌ ${err.message}`, "error");
  }
}

function escJs(str) {
  return String(str).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

// ─── Connect / Disconnect ─────────────────────────────────────

async function doMT5Connect() {
  const login = parseInt($id("mt5-login").value) || 0;
  const password = $id("mt5-password").value || "";
  const server = $id("mt5-server").value || "";

  const btn = document.querySelector("#mt5-tab-connect .btn-primary");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Connecting…";
  }

  try {
    const res = await fetch(`${API_BASE}/mt5/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, password, server }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Connection failed");

    updateConnectionStatus(data.connected, data.simulation_mode);
    showToast(
      data.simulation_mode
        ? "🔌 Connected (Simulation)"
        : "✅ Connected to MT5 Live",
      "success",
    );
    closeMT5Panel();
  } catch (err) {
    showToast(`❌ ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Connect";
    }
  }
}

async function doMT5Disconnect() {
  try {
    await fetch(`${API_BASE}/mt5/disconnect`, { method: "POST" });
    updateConnectionStatus(false, false);
    showToast("🔌 Disconnected from MT5", "info");
    closeMT5Panel();
  } catch (err) {
    showToast("❌ Disconnect failed", "error");
  }
}

function updateConnectionStatus(connected, simulationMode) {
  const icon = $id("conn-status-icon");
  const text = $id("conn-status-text");
  const badge = $id("conn-mode-badge");
  const simBadge = $id("badge-sim");

  // simBadge is always hidden — simulation mode is not exposed in the UI
  if (simBadge) simBadge.style.display = "none";

  if (connected) {
    icon.textContent = "🟢";
    text.textContent = "Connected to MT5";
    if (badge) badge.style.display = "none";
    // Auto-dismiss login modal when connection is established
    if (_loginRequired) {
      _loginRequired = false;
      const modal = $id("mt5-modal");
      if (modal) modal.classList.remove("show", "login-required");
      const notice = $id("mt5-login-notice");
      if (notice) notice.style.display = "none";
    }
  } else {
    icon.textContent = "🔴";
    text.textContent = "Disconnected";
    if (badge) badge.style.display = "none";
  }
}

/* ═══════════════════════════════════════════════════════════
   AI Settings Modal
   ═══════════════════════════════════════════════════════════ */

async function openAISettings() {
  $id("ai-settings-modal").classList.add("show");
  // Load provider settings first, then show provider pane
  await loadProviderSettings();
  switchAIPane("provider");
}

function closeAISettings(e) {
  if (!e || e.target === $id("ai-settings-modal"))
    $id("ai-settings-modal").classList.remove("show");
}

// ─── AI Pane Navigation ───────────────────────────────────────
function switchAIPane(pane) {
  document
    .querySelectorAll(".ai-side-btn")
    .forEach((b) => b.classList.remove("active"));
  document
    .querySelectorAll(".ai-modal-pane")
    .forEach((p) => p.classList.remove("active"));

  const btn = document.querySelector(`.ai-side-btn[data-aipane="${pane}"]`);
  if (btn) btn.classList.add("active");
  const panel = $id(`ai-pane-${pane}`);
  if (panel) panel.classList.add("active");

  if (pane === "symbols") loadAISymbolSettings();
  if (pane === "strategy") loadStrategyConfig();
}

// ─── Provider Selection ──────────────────────────────────────
function selectProvider(name) {
  currentProvider = name;
  document
    .querySelectorAll(".provider-btn")
    .forEach((b) => b.classList.remove("active"));
  const btn = $id(`prov-btn-${name}`);
  if (btn) btn.classList.add("active");

  const mmConf = $id("minimax-config");
  const gmConf = $id("gemini-config");
  if (mmConf) mmConf.style.display = name === "minimax" ? "" : "none";
  if (gmConf) gmConf.style.display = name === "gemini" ? "" : "none";
}

// ─── Load Provider Settings ───────────────────────────────────
async function loadProviderSettings() {
  try {
    const res = await fetch(`${API_BASE}/ai/provider`);
    const data = await res.json();

    currentProvider = data.provider || "minimax";
    selectProvider(currentProvider);

    // Populate form fields (mask key if already set)
    const mmKey = $id("minimax-api-key");
    if (mmKey)
      mmKey.placeholder = data.minimax_api_key
        ? "(key saved)"
        : "Enter MiniMax API key";
    const mmMod = $id("minimax-model");
    if (mmMod) mmMod.value = data.minimax_model || "MiniMax-Text-01";

    const gmKey = $id("gemini-api-key");
    if (gmKey)
      gmKey.placeholder = data.gemini_api_key
        ? "(key saved)"
        : "Enter Gemini API key";
    const gmMod = $id("gemini-model");
    if (gmMod) gmMod.value = data.gemini_model || "gemini-1.5-flash";

    const intv = $id("ai-analysis-interval");
    if (intv) intv.value = data.analysis_interval || 60;

    // Update master toggle
    const masterSwitch = $id("ai-master-switch");
    if (masterSwitch) masterSwitch.checked = !!data.auto_trade_enabled;
    updateAIMasterBox(!!data.auto_trade_enabled);

    // Update info panel on AI tab
    const provName = $id("ai-provider-name");
    if (provName)
      provName.textContent =
        currentProvider === "minimax" ? "MiniMax" : "Gemini";
    const keyStatus = $id("ai-key-status");
    const hasKey =
      currentProvider === "minimax"
        ? !!data.minimax_api_key
        : !!data.gemini_api_key;
    if (keyStatus) {
      keyStatus.textContent = hasKey ? "API Key: Set" : "API Key: Not set";
      keyStatus.style.color = hasKey
        ? "var(--accent-green)"
        : "var(--accent-red)";
    }
    const intEl = $id("ai-interval-val");
    if (intEl) intEl.textContent = `${data.analysis_interval || 60}s`;
  } catch (e) {
    console.error("loadProviderSettings failed", e);
  }
}

// ─── Save Provider Settings ───────────────────────────────────
async function saveProviderSettings() {
  const resultEl = $id("provider-test-result");
  if (resultEl) {
    resultEl.textContent = "Saving…";
    resultEl.style.color = "var(--text-dim)";
  }

  const payload = { provider: currentProvider };
  const mmKey = $id("minimax-api-key")?.value.trim();
  if (mmKey) payload.minimax_api_key = mmKey;
  const mmMod = $id("minimax-model")?.value;
  if (mmMod) payload.minimax_model = mmMod;
  const gmKey = $id("gemini-api-key")?.value.trim();
  if (gmKey) payload.gemini_api_key = gmKey;
  const gmMod = $id("gemini-model")?.value;
  if (gmMod) payload.gemini_model = gmMod;
  const intv = parseInt($id("ai-analysis-interval")?.value);
  if (!isNaN(intv)) payload.analysis_interval = intv;

  try {
    const res = await fetch(`${API_BASE}/ai/provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (resultEl) {
      resultEl.textContent = "✅ Settings saved";
      resultEl.style.color = "var(--accent-green)";
    }
    showToast("AI provider settings saved", "success");
    // Clear key fields after save
    if (mmKey && $id("minimax-api-key")) {
      $id("minimax-api-key").value = "";
      $id("minimax-api-key").placeholder = "(key saved)";
    }
    if (gmKey && $id("gemini-api-key")) {
      $id("gemini-api-key").value = "";
      $id("gemini-api-key").placeholder = "(key saved)";
    }
    // Refresh info panel
    await loadProviderSettings();
  } catch (e) {
    if (resultEl) {
      resultEl.textContent = "❌ Save failed";
      resultEl.style.color = "var(--accent-red)";
    }
    showToast("Failed to save AI settings", "error");
  }
}

// ─── Test AI Connection ───────────────────────────────────────
async function testAIConnection() {
  const resultEl = $id("provider-test-result");
  if (resultEl) {
    resultEl.textContent = "Testing…";
    resultEl.style.color = "var(--text-dim)";
  }
  try {
    const res = await fetch(`${API_BASE}/ai/analyze/BTCUSD`, {
      method: "POST",
    });
    const data = await res.json();
    if (data.signal) {
      const conf = data.confidence || 0;
      if (resultEl) {
        resultEl.textContent = `✅ OK — BTCUSD: ${data.signal} (${conf}% confidence)`;
        resultEl.style.color = "var(--accent-green)";
      }
    } else {
      const msg = data.error || data.detail || "Unknown error";
      if (resultEl) {
        resultEl.textContent = `⚠️ ${msg}`;
        resultEl.style.color = "var(--accent-orange)";
      }
    }
  } catch (e) {
    if (resultEl) {
      resultEl.textContent = "❌ Connection failed";
      resultEl.style.color = "var(--accent-red)";
    }
  }
}

// ─── Load AI Symbol Settings (modal symbols pane) ─────────────
async function loadAISymbolSettings() {
  const container = $id("ai-symbol-settings-list");
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner"></div>';

  try {
    const [settingsRes, analysisRes] = await Promise.all([
      fetch(`${API_BASE}/ai/provider`),
      fetch(`${API_BASE}/ai/analysis`),
    ]);
    const settings = await settingsRes.json();
    const analysis = await analysisRes.json();
    const syms = settings.symbols || {};

    container.innerHTML = SYMBOLS.map((sym) => {
      const cfg = syms[sym] || {
        auto_trade: false,
        lot_size: 0.1,
        sl_points: 20,
        tp_points: 35,
        max_trades: 1,
      };
      const an = analysis[sym] || null;
      return renderAISymbolSettingsCard(sym, cfg, an);
    }).join("");
  } catch (e) {
    container.innerHTML =
      '<p style="color:var(--accent-red);padding:12px">Failed to load symbol settings</p>';
  }
}

// ─── Render Symbol Settings Card (modal) ─────────────────────
function renderAISymbolSettingsCard(sym, cfg, analysis) {
  const sigBadge = analysis
    ? `<span class="ai-signal ${analysis.signal}">${
        analysis.signal
      }</span> <span style="font-size:11px;color:var(--text-dim)">${
        analysis.confidence || 0
      }%</span>`
    : `<span style="font-size:11px;color:var(--text-dim)">No analysis yet</span>`;

  return `
    <div class="ai-sym-card${
      cfg.auto_trade ? " has-auto-trade" : ""
    }" id="ai-sym-card-${sym}">
      <div class="ai-sym-header">
        <span class="ai-sym-name">${sym}</span>
        ${sigBadge}
        <label class="toggle-switch" style="margin-left:auto">
          <input type="checkbox" id="ai-sym-${sym}-auto" ${
            cfg.auto_trade ? "checked" : ""
          }
                 onchange="saveAISymbolSettings('${sym}')">
          <span class="toggle-slider"></span>
        </label>
        <span style="font-size:11px;color:var(--text-dim);min-width:60px" id="ai-sym-${sym}-lbl">
          ${cfg.auto_trade ? "Auto: ON" : "Auto: OFF"}
        </span>
      </div>
      <div class="ai-sym-controls">
        <div>
          <label>Lot</label>
          <input type="number" id="ai-sym-${sym}-lot" value="${cfg.lot_size}"
                 min="0.01" max="10" step="0.01" class="form-input"
                 style="width:100%" onchange="saveAISymbolSettings('${sym}')">
        </div>
        <div>
          <label>SL pts</label>
          <input type="number" id="ai-sym-${sym}-sl" value="${cfg.sl_points}"
                 min="1" step="1" class="form-input"
                 style="width:100%" onchange="saveAISymbolSettings('${sym}')">
        </div>
        <div>
          <label>TP pts</label>
          <input type="number" id="ai-sym-${sym}-tp" value="${cfg.tp_points}"
                 min="1" step="1" class="form-input"
                 style="width:100%" onchange="saveAISymbolSettings('${sym}')">
        </div>
        <div>
          <label>Max trades</label>
          <input type="number" id="ai-sym-${sym}-max" value="${
            cfg.max_trades || 1
          }"
                 min="1" max="10" step="1" class="form-input"
                 style="width:100%" onchange="saveAISymbolSettings('${sym}')">
        </div>
      </div>
    </div>`;
}

// ─── Save AI Symbol Settings ──────────────────────────────────
async function saveAISymbolSettings(sym) {
  const auto = $id(`ai-sym-${sym}-auto`)?.checked ?? false;
  const lot_size = parseFloat($id(`ai-sym-${sym}-lot`)?.value) || 0.1;
  const sl_points = parseInt($id(`ai-sym-${sym}-sl`)?.value) || 20;
  const tp_points = parseInt($id(`ai-sym-${sym}-tp`)?.value) || 35;
  const max_trades = parseInt($id(`ai-sym-${sym}-max`)?.value) || 1;

  const lbl = $id(`ai-sym-${sym}-lbl`);
  if (lbl) lbl.textContent = auto ? "Auto: ON" : "Auto: OFF";
  const card = $id(`ai-sym-card-${sym}`);
  if (card) card.classList.toggle("has-auto-trade", auto);

  try {
    await fetch(`${API_BASE}/ai/symbol`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: sym,
        auto_trade: auto,
        lot_size,
        sl_points,
        tp_points,
        max_trades,
      }),
    });
    showToast(`${sym} AI settings saved`, "success");
  } catch {
    showToast(`Failed to save ${sym} settings`, "error");
  }
}

// ─── Master Auto-Trade Toggle ─────────────────────────────────
async function toggleAIMaster() {
  const enabled = $id("ai-master-switch")?.checked ?? false;
  updateAIMasterBox(enabled);
  try {
    await fetch(`${API_BASE}/ai/provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto_trade_enabled: enabled }),
    });
    showToast(
      enabled ? "🤖 AI Auto Trade enabled" : "AI Auto Trade disabled",
      enabled ? "success" : "info",
    );
  } catch {
    showToast("Failed to toggle AI auto trade", "error");
  }
}

function updateAIMasterBox(enabled) {
  const box = $id("ai-master-box");
  if (box) box.classList.toggle("enabled", enabled);
  const statusEl = $id("ai-master-status");
  if (statusEl)
    statusEl.textContent = enabled
      ? "Active — AI is monitoring markets"
      : "Disabled — Manual mode only";
}

// ─── Analyze All Symbols ──────────────────────────────────────
async function analyzeAllSymbols() {
  showToast("Analyzing all symbols…", "info");
  try {
    await Promise.all(
      SYMBOLS.map((sym) =>
        fetch(`${API_BASE}/ai/analyze/${sym}`, { method: "POST" }),
      ),
    );
    // Reload analysis and refresh grid
    const res = await fetch(`${API_BASE}/ai/analysis`);
    const analysis = await res.json();
    const settRes = await fetch(`${API_BASE}/ai/provider`);
    const settings = await settRes.json();
    renderAISymbolsGrid(settings, analysis);
    showToast("Analysis complete", "success");
  } catch {
    showToast("Analysis failed", "error");
  }
}

// ─── Render AI Symbols Grid (AI Auto Trade tab) ───────────────
function renderAISymbolsGrid(aiSettings, aiAnalysis) {
  const grid = $id("ai-symbols-grid");
  if (!grid) return;
  const syms = aiSettings && aiSettings.symbols ? aiSettings.symbols : {};

  grid.innerHTML = SYMBOLS.map((sym) => {
    const cfg = syms[sym] || { auto_trade: false, lot_size: 0.1 };
    const an = aiAnalysis && aiAnalysis[sym] ? aiAnalysis[sym] : null;
    const sig = an ? an.signal : "HOLD";
    const conf = an ? an.confidence || 0 : 0;
    const reason = an ? an.reason || "" : "No analysis yet";
    const risk = an ? an.risk || "" : "";
    const riskCls =
      risk === "HIGH"
        ? "var(--accent-red)"
        : risk === "MEDIUM"
          ? "var(--accent-orange)"
          : "var(--accent-green)";

    return `
        <div class="ai-sym-card${cfg.auto_trade ? " has-auto-trade" : ""}">
          <div class="ai-sym-header">
            <span class="ai-sym-name">${sym}</span>
            <span class="ai-signal ${sig}">${sig}</span>
          </div>
          <div class="ai-sym-analysis">
            <div class="ai-conf-bar">
              <div class="ai-conf-fill" style="width:${conf}%;background:${
                conf >= 70
                  ? "var(--accent-green)"
                  : conf >= 50
                    ? "var(--accent-orange)"
                    : "var(--accent-red)"
              }"></div>
            </div>
            <span style="font-size:11px;color:var(--text-dim)">${conf}% confidence</span>
            ${
              risk
                ? `<span style="font-size:11px;color:${riskCls};margin-left:8px">Risk: ${risk}</span>`
                : ""
            }
          </div>
          <div class="ai-reason">${reason}</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:6px">
            Auto: ${
              cfg.auto_trade
                ? '<span style="color:var(--accent-green)">ON</span>'
                : "OFF"
            }
            &nbsp;|&nbsp; Lot: ${cfg.lot_size}
          </div>
        </div>`;
  }).join("");
}

// ─── Update AI Auto Trade Tab (from realtime data) ────────────
function updateAIAutoTab(data) {
  const analysis = data.ai_analysis || {};
  const enabled = !!data.ai_auto_trade;

  // Master box
  const masterSwitch = $id("ai-master-switch");
  if (masterSwitch && masterSwitch.checked !== enabled)
    masterSwitch.checked = enabled;
  updateAIMasterBox(enabled);

  // Symbols grid — only if it has no rendered cards yet, or update signals
  const grid = $id("ai-symbols-grid");
  if (grid && grid.children.length === 0) {
    // First paint: need settings too — fetch async
    fetch(`${API_BASE}/ai/provider`)
      .then((r) => r.json())
      .then((settings) => {
        renderAISymbolsGrid(settings, analysis);
      })
      .catch(() => {});
  } else if (grid) {
    // Update existing cards: just update badges/bars
    SYMBOLS.forEach((sym) => {
      const an = analysis[sym];
      if (!an) return;
      const card = grid.querySelector(`.ai-sym-card .ai-sym-name`);
      // Re-render is simplest; avoid partial update complexity
    });
  }
}

// ─── Load AI Log ──────────────────────────────────────────────
async function loadAILog() {
  const list = $id("ai-log-list");
  if (!list) return;
  list.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const res = await fetch(`${API_BASE}/ai/log`);
    const data = await res.json();
    const log = data.log || [];
    if (!log.length) {
      list.innerHTML =
        '<div class="ai-log-entry"><span class="ai-log-msg" style="color:var(--text-dim)">No activity yet</span></div>';
      return;
    }
    list.innerHTML = [...log]
      .reverse()
      .map(
        (entry) => `
            <div class="ai-log-entry${entry.action ? " trade" : ""}">
              <span class="ai-log-time">${
                entry.timestamp ? entry.timestamp.substring(11, 19) : ""
              }</span>
              <span class="ai-log-sym">${entry.symbol || ""}</span>
              <span class="ai-signal ${
                entry.signal || "HOLD"
              }" style="font-size:10px">${entry.signal || ""}</span>
              <span class="ai-log-msg">${
                entry.action ? entry.action + " — " : ""
              }${entry.reason || ""}</span>
              ${
                entry.confidence
                  ? `<span style="margin-left:auto;font-size:10px;color:var(--text-dim)">${entry.confidence}%</span>`
                  : ""
              }
            </div>`,
      )
      .join("");
  } catch {
    list.innerHTML =
      '<div class="ai-log-entry"><span class="ai-log-msg" style="color:var(--accent-red)">Failed to load log</span></div>';
  }
}

// Legacy helpers (kept for compatibility with any old WS events)
function renderAISettings(settings) {
  /* replaced by new functions above */
}
function toggleAISetting(symbol) {}
function saveAISetting(symbol) {
  saveAISymbolSettings(symbol);
}

// ─── Strategy Config Pane ─────────────────────────────────────
async function loadStrategyConfig() {
  const body = $id("ai-settings-body");
  if (!body) return;
  body.innerHTML = '<div class="loading-spinner"></div>';

  try {
    const res = await fetch(`${API_BASE}/ai/settings`);
    const settings = await res.json();

    body.innerHTML = settings
      .map(
        (s) => `
      <div class="ai-sym-card" id="strat-card-${s.symbol}" style="margin-bottom:10px">
        <div class="ai-sym-header">
          <span class="ai-sym-name">${s.icon || ""} ${s.symbol}</span>
          <span style="font-size:11px;color:var(--text-dim);margin-left:4px">${s.name || ""}</span>
          <label class="toggle-switch" style="margin-left:auto">
            <input type="checkbox" id="strat-${s.symbol}-en" ${s.enabled ? "checked" : ""}
                   onchange="saveStrategyConfig('${s.symbol}')">
            <span class="toggle-slider"></span>
          </label>
          <span style="font-size:11px;color:var(--text-dim);min-width:44px" id="strat-${s.symbol}-lbl">
            ${s.enabled ? "ON" : "OFF"}
          </span>
        </div>
        <div class="ai-sym-controls" style="grid-template-columns:repeat(4,1fr)">
          <div>
            <label>Lot</label>
            <input type="number" id="strat-${s.symbol}-lot" value="${s.lot_size}"
                   min="0.01" max="10" step="0.01" class="form-input" style="width:100%"
                   onchange="saveStrategyConfig('${s.symbol}')">
          </div>
          <div>
            <label>SL pts</label>
            <input type="number" id="strat-${s.symbol}-sl" value="${s.sl_points}"
                   min="1" step="1" class="form-input" style="width:100%"
                   onchange="saveStrategyConfig('${s.symbol}')">
          </div>
          <div>
            <label>TP pts</label>
            <input type="number" id="strat-${s.symbol}-tp" value="${s.tp_points}"
                   min="1" step="1" class="form-input" style="width:100%"
                   onchange="saveStrategyConfig('${s.symbol}')">
          </div>
          <div>
            <label>Cooldown (s)</label>
            <input type="number" id="strat-${s.symbol}-cd" value="${s.cooldown}"
                   min="10" step="10" class="form-input" style="width:100%"
                   onchange="saveStrategyConfig('${s.symbol}')">
          </div>
        </div>
      </div>`,
      )
      .join("");
  } catch {
    body.innerHTML =
      '<p style="color:var(--accent-red);padding:12px">Failed to load strategy config</p>';
  }
}

async function saveStrategyConfig(symbol) {
  const enabled = $id(`strat-${symbol}-en`)?.checked ?? true;
  const lot_size = parseFloat($id(`strat-${symbol}-lot`)?.value) || 0.01;
  const sl_points = parseInt($id(`strat-${symbol}-sl`)?.value) || 100;
  const tp_points = parseInt($id(`strat-${symbol}-tp`)?.value) || 200;
  const cooldown = parseInt($id(`strat-${symbol}-cd`)?.value) || 60;

  const lbl = $id(`strat-${symbol}-lbl`);
  if (lbl) lbl.textContent = enabled ? "ON" : "OFF";

  try {
    await fetch(`${API_BASE}/ai/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol,
        enabled,
        lot_size,
        sl_points,
        tp_points,
        cooldown,
      }),
    });
    showToast(`${symbol} strategy saved`, "success");
  } catch {
    showToast(`Failed to save ${symbol}`, "error");
  }
}

/* ═══════════════════════════════════════════════════════════
   Other Modals
   ═══════════════════════════════════════════════════════════ */

async function openRetrain() {
  $id("retrain-modal").classList.add("show");
  $id("retrain-body").innerHTML = '<div class="loading-spinner"></div>';
  try {
    const res = await fetch(`${API_BASE}/insights/retrain`);
    const data = await res.json();
    $id("retrain-body").innerHTML = data.suggestions?.length
      ? data.suggestions
          .map((s) => `<div class="suggestion-item">${s}</div>`)
          .join("")
      : '<div class="suggestion-item">✅ All systems optimal</div>';
  } catch {
    $id("retrain-body").innerHTML =
      '<div class="suggestion-item">❌ Failed to fetch</div>';
  }
}

function closeRetrain(e) {
  if (!e || e.target === $id("retrain-modal"))
    $id("retrain-modal").classList.remove("show");
}

/* ═══════════════════════════════════════════════════════════
   Actions
   ═══════════════════════════════════════════════════════════ */

function toggleSystem() {
  sendCmd("toggle_system");
}
function toggleStrategy(symbol) {
  sendCmd("toggle_strategy", { symbol });
}

function closePosition(ticket, force = false) {
  if (force && !forceCloseEnabled) {
    alert(
      "⚠️ Force Close ถูกปิดใช้งานอยู่\nเปิดใช้งานได้ที่หน้า 'พอร์ตที่เปิดอยู่'",
    );
    return;
  }
  const msg = force ? "Force close (ข้ามสัญญาณออก)?" : "ปิดพอร์ต?";
  if (confirm(`${msg} #${ticket}?`))
    sendCmd("close_position", { ticket, force });
}

function toggleForceClose() {
  forceCloseEnabled = !forceCloseEnabled;
  storage_set(StorageKeys.FORCE_CLOSE_ENABLED, forceCloseEnabled);
  // Sync both toggles (positions page + dashboard)
  const t1 = $id("toggle-force-close");
  const t2 = $id("toggle-force-close-dash");
  if (t1) t1.checked = forceCloseEnabled;
  if (t2) t2.checked = forceCloseEnabled;
  // Re-render positions so Force button appears/disappears immediately
  const cachedPositions = window._lastPositions;
  if (cachedPositions) updatePositions(cachedPositions);
}

/* ═══════════════════════════════════════════════════════════
   UI Helpers
   ═══════════════════════════════════════════════════════════ */

function updateSystemButton() {
  const btn = $id("btn-system");
  const text = $id("btn-system-text");
  btn.classList.toggle("off", !systemActive);
  text.textContent = systemActive ? "ON" : "OFF";
}

function updateMT5Badge(connected) {
  const badge = $id("badge-mt5");
  badge.classList.toggle("offline", !connected);
  badge.title = connected ? "MT5 Online" : "MT5 Offline";
}

function animateValue(el, newVal) {
  if (!el || el.textContent === newVal) return;
  el.style.opacity = "0.5";
  el.textContent = newVal;
  requestAnimationFrame(() => {
    el.style.transition = "opacity 0.25s";
    el.style.opacity = "1";
  });
}

function fmt(num) {
  return Number(num).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function showToast(msg, type = "info") {
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.textContent = msg;
  $id("toast-container").appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

/* ═══════════════════════════════════════════════════════════
   Keyboard Shortcuts
   ═══════════════════════════════════════════════════════════ */

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    // Don't close MT5 modal if login is required (no connection yet)
    if (!_loginRequired) $id("mt5-modal")?.classList.remove("show");
    ["ai-settings-modal", "retrain-modal"].forEach((id) => {
      $id(id)?.classList.remove("show");
    });
  }
  if (e.key === " " && e.target === document.body) {
    e.preventDefault();
    toggleSystem();
  }
});

/* ═══════════════════════════════════════════════════════════
   Bootstrap
   ═══════════════════════════════════════════════════════════ */

async function fetchInitialData() {
  try {
    const [account, strategies, status, insights, prices] = await Promise.all([
      fetch(`${API_BASE}/account`).then((r) => r.json()),
      fetch(`${API_BASE}/strategies`).then((r) => r.json()),
      fetch(`${API_BASE}/status`).then((r) => r.json()),
      fetch(`${API_BASE}/insights`).then((r) => r.json()),
      fetch(`${API_BASE}/symbols`).then((r) => r.json()),
    ]);

    const balFmt = `$${fmt(account.balance || 0)}`;
    animateValue($id("account-balance"), balFmt);
    animateValue($id("account-equity"), `$${fmt(account.equity || 0)}`);
    const dashBal = $id("dash-balance");
    if (dashBal) animateValue(dashBal, balFmt);
    $id("win-rate").textContent = `${insights.win_rate || 0}%`;
    $id("total-trades").textContent = insights.total_trades || 0;

    systemActive = status.system_active;
    updateSystemButton();
    updateMT5Badge(status.mt5_connected);
    updateConnectionStatus(status.mt5_connected, status.simulation_mode);
    // Auto-open login modal if MT5 not connected
    if (!status.mt5_connected) openMT5LoginPrompt();

    updateStrategies(strategies);
    updateInsights(insights);

    latestPrices = prices;
    updateTickerBar(prices);
  } catch (e) {
    console.error("Initial fetch failed", e);
    showToast("⚠️ Cannot connect to server", "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  connectWebSocket();
  fetchInitialData();
  // Hash-based routing: activate the tab from URL hash on load
  const initialTab = window.location.hash.replace("#", "") || "dashboard";
  switchTab(initialTab);
  // Support browser back/forward navigation
  window.addEventListener("popstate", () => {
    const tab = window.location.hash.replace("#", "") || "dashboard";
    switchTab(tab);
  });
});

/* ═══════════════════════════════════════════════════════════
   Telegram Notifications
   ═══════════════════════════════════════════════════════════ */

async function loadTelegramSettings() {
  try {
    const res = await fetch(`${API_BASE}/telegram/settings`);
    const data = await res.json();
    _applyTelegramSettings(data);
  } catch (e) {
    console.error("loadTelegramSettings failed", e);
    _showTgBanner("❌ ไม่สามารถโหลดการตั้งค่าได้", "var(--accent-red)");
  }
}

function _applyTelegramSettings(data) {
  const enEl = $id("tg-enabled");
  const chatEl = $id("tg-chat-id");
  const savedEl = $id("tg-token-saved");

  if (enEl) enEl.checked = !!data.enabled;
  if (chatEl) chatEl.value = data.chat_id || "";

  // Show "token saved" indicator if a token exists on server
  if (savedEl) savedEl.style.display = data.has_token ? "" : "none";
  // Clear the token input (never pre-fill it for security)
  const tokenEl = $id("tg-token");
  if (tokenEl) tokenEl.value = "";

  // Notification type checkboxes
  const map = {
    "tg-notify-open": "notify_open",
    "tg-notify-close": "notify_close",
    "tg-notify-strategy": "notify_strategy",
    "tg-notify-risk": "notify_risk",
  };
  for (const [id, key] of Object.entries(map)) {
    const el = $id(id);
    if (el) el.checked = data[key] !== false; // default true
  }

  _updateTgEnabledLabel(!!data.enabled);
}

function _updateTgEnabledLabel(enabled) {
  const lbl = $id("tg-enabled-label");
  if (!lbl) return;
  lbl.textContent = enabled ? "เปิดใช้งาน ✅" : "ปิดใช้งาน";
  lbl.style.color = enabled ? "var(--accent-green)" : "var(--text-dim)";
}

function _showTgBanner(msg, color = "var(--accent-green)") {
  const banner = $id("tg-status-banner");
  const text = $id("tg-status-text");
  if (!banner || !text) return;
  text.textContent = msg;
  text.style.color = color;
  banner.style.display = "";
  setTimeout(() => {
    banner.style.display = "none";
  }, 4000);
}

async function saveTelegramSettings() {
  const tokenEl = $id("tg-token");
  const chatEl = $id("tg-chat-id");
  const enEl = $id("tg-enabled");

  const payload = {
    enabled: enEl?.checked ?? false,
    chat_id: chatEl?.value.trim() || "",
    notify_open: $id("tg-notify-open")?.checked ?? true,
    notify_close: $id("tg-notify-close")?.checked ?? true,
    notify_strategy: $id("tg-notify-strategy")?.checked ?? true,
    notify_risk: $id("tg-notify-risk")?.checked ?? true,
  };

  // Only include token if user actually typed one
  const rawToken = tokenEl?.value.trim();
  if (rawToken) payload.bot_token = rawToken;

  try {
    const res = await fetch(`${API_BASE}/telegram/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    _applyTelegramSettings(data);
    _updateTgEnabledLabel(payload.enabled);
    _showTgBanner("✅ บันทึกการตั้งค่าเรียบร้อย");
    showToast("Telegram settings saved", "success");
  } catch (e) {
    _showTgBanner("❌ บันทึกไม่สำเร็จ", "var(--accent-red)");
    showToast("Failed to save Telegram settings", "error");
  }
}

async function testTelegram() {
  const btn = $id("tg-test-btn");
  const result = $id("tg-test-result");

  // Save first so latest token/chat_id is used
  await saveTelegramSettings();

  if (btn) {
    btn.disabled = true;
    btn.textContent = "กำลังส่ง…";
  }
  if (result) {
    result.style.display = "";
    result.textContent = "";
  }

  try {
    const res = await fetch(`${API_BASE}/telegram/test`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      if (result) {
        result.textContent = "✅ ส่งข้อความสำเร็จ! ตรวจสอบใน Telegram";
        result.style.color = "var(--accent-green)";
      }
      showToast("✅ Telegram test sent!", "success");
    } else {
      const err = await res.json();
      const msg = err.detail || "Unknown error";
      if (result) {
        result.textContent = `❌ ${msg}`;
        result.style.color = "var(--accent-red)";
      }
      showToast(`Telegram test failed: ${msg}`, "error");
    }
  } catch (e) {
    if (result) {
      result.textContent = "❌ ไม่สามารถเชื่อมต่อ server ได้";
      result.style.color = "var(--accent-red)";
    }
    showToast("Connection error", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "📤 ทดสอบส่งข้อความ";
    }
  }
}

function toggleTgTokenVisibility() {
  const input = $id("tg-token");
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
}

function toggleTgGuide() {
  const guide = $id("tg-guide");
  const btn = $id("tg-guide-btn");
  if (!guide || !btn) return;
  const show = guide.style.display === "none";
  guide.style.display = show ? "" : "none";
  btn.textContent = show ? "ซ่อน" : "แสดง";
}
