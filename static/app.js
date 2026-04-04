/* ═══════════════════════════════════════════════════════════
   pytradeAI — Frontend Application
   Real-time MT5 dashboard with manual trading & AI settings
   ═══════════════════════════════════════════════════════════ */

// ─── Config ──────────────────────────────────────────────────
const WS_URL = `ws://${window.location.host}/ws`;
const API_BASE = `http://${window.location.host}/api`;

// ─── State ───────────────────────────────────────────────────
let ws = null;
let systemActive = false;
let reconnectAttempts = 0;
let latestPrices = {}; // { BTCUSD: {bid,ask,spread}, ... }
let aiSettingsCache = []; // latest AI settings from server
let currentProvider = "minimax"; // active AI provider selection
let aiThinkingLog = []; // AI reasoning/thinking process log
const MAX_RECONNECT = 50;

// ─── Constants ───────────────────────────────────────────────
const SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD", "ETHUSD"];

// ─── LocalStorage Management ──────────────────────────────────
const StorageKeys = {
  ACCOUNTS: "pytrade_accounts",
  AI_SETTINGS: "pytrade_ai_settings",
  STRATEGY_SETTINGS: "pytrade_strategy_settings",
  SYSTEM_LOG: "pytrade_system_log",
  AI_THINKING_LOG: "pytrade_ai_thinking_log",
  TODAY_TRADES: "pytrade_today_trades",
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

// ─── DOM helpers ─────────────────────────────────────────────
const $id = (id) => document.getElementById(id);

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
          <td class="log-detail">${escHtml(e.detail || "")}</td>
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
    <td class="log-detail">${escHtml(e.detail || "")}</td>`;
  tbody.prepend(tr);
}

function clearLogDisplay() {
  const tbody = $id("log-tbody");
  if (tbody)
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><span class="empty-icon">📋</span>View cleared — click Refresh to reload</div></td></tr>`;
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

  const todayTrades = allTrades.filter(
    (t) => t.time >= todayStart && t.time < todayEnd,
  );

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

    // Trade tab account info panel
    const trBal = $id("trade-acct-balance");
    if (trBal) trBal.textContent = balFmt;
    const trEq = $id("trade-acct-equity");
    if (trEq) trEq.textContent = eqFmt;
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
    updateTradePriceDisplay();
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
  USDJPY: "¥",
  ETHUSD: "Ξ",
  EURUSD: "€",
  GBPUSD: "£",
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

function updateTradePriceDisplay() {
  const sym = $id("trade-symbol")?.value;
  if (!sym || !latestPrices[sym]) return;
  const p = latestPrices[sym];
  const digits = sym.includes("JPY")
    ? 3
    : sym.includes("BTC") || sym.includes("ETH") || sym.includes("XAU")
      ? 2
      : 5;
  $id("trade-bid").textContent = p.bid.toFixed(digits);
  $id("trade-ask").textContent = p.ask.toFixed(digits);
}

function onSymbolChange() {
  updateTradePriceDisplay();
}

/* ═══════════════════════════════════════════════════════════
   Strategies Grid
   ═══════════════════════════════════════════════════════════ */

function _buildStrategyHTML(s, suffix) {
  return `
    <div class="strategy-item" id="strat-${suffix}-${s.symbol}">
        <div class="strategy-info">
            <span class="strategy-icon">${s.icon}</span>
            <div>
                <div class="strategy-name">${s.symbol}</div>
                <div class="strategy-detail">${s.name || ""}</div>
            </div>
        </div>
        <button class="strategy-toggle ${s.enabled ? "on" : ""}"
                onclick="toggleStrategy('${s.symbol}')"
                id="strat-toggle-${suffix}-${s.symbol}">
            ${s.enabled ? "ON" : "OFF"}
        </button>
    </div>`;
}

function updateStrategies(strategies) {
  // Dashboard grid
  const grid = $id("strategies-grid");
  if (grid) {
    grid.innerHTML = strategies
      .map((s) => _buildStrategyHTML(s, "dash"))
      .join("");
  }
  // Full strategies tab grid
  const gridFull = $id("strategies-grid-full");
  if (gridFull) {
    gridFull.innerHTML = strategies
      .map((s) => _buildStrategyHTML(s, "full"))
      .join("");
  }
  // Update active strategy count
  const activeCount = strategies.filter((s) => s.enabled).length;
  const dashActive = $id("dash-strategies-active");
  if (dashActive)
    dashActive.textContent = `${activeCount}/${strategies.length}`;

  // Load trading conditions for each symbol
  loadAllTradingConditions(strategies);
}

async function loadAllTradingConditions(strategies) {
  const container = $id("trading-conditions");
  if (!container) return;

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
      .map((c) => _buildConditionCard(c))
      .join("");
  } catch (err) {
    console.error("Failed to load trading conditions:", err);
  }
}

function _buildConditionCard(cond) {
  if (cond.status !== "ready") {
    return `
      <div class="trading-condition-card">
        <div class="tc-header">
          <span class="tc-symbol">${cond.symbol}</span>
        </div>
        <div style="font-size:11px; color:var(--text-muted)">⚠️ ${cond.message || "No data"}</div>
      </div>`;
  }

  const indicators = cond.technical_indicators;
  const buy = cond.buy_signal;
  const sell = cond.sell_signal;

  const buyTriggered = buy.triggered ? "buy" : "neutral";
  const sellTriggered = sell.triggered ? "sell" : "neutral";

  return `
    <div class="trading-condition-card">
      <div class="tc-header">
        <span class="tc-symbol">${cond.symbol}</span>
        <span class="tc-price">$${cond.current_price}</span>
      </div>
      
      <div class="tc-indicators">
        <div class="tc-ind-item">
          <div class="tc-ind-label">RSI-14</div>
          <div class="tc-ind-value">${indicators.rsi_14.toFixed(1)}</div>
        </div>
        <div class="tc-ind-item">
          <div class="tc-ind-label">MA 7 / 20</div>
          <div class="tc-ind-value">${indicators.ma_7.toFixed(5)} / ${indicators.ma_20.toFixed(5)}</div>
        </div>
        <div class="tc-ind-item">
          <div class="tc-ind-label">BB Upper</div>
          <div class="tc-ind-value">${indicators.bb_upper.toFixed(5)}</div>
        </div>
        <div class="tc-ind-item">
          <div class="tc-ind-label">BB Lower</div>
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
    const allTrades = await res.json();

    if (!Array.isArray(allTrades)) {
      allTrades = [];
    }

    // Filter trades from today only
    const now = new Date();
    const todayStart =
      new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() /
      1000;
    const todayEnd = todayStart + 86400; // 24 hours

    const todayTrades = allTrades.filter(
      (t) => t.time >= todayStart && t.time < todayEnd,
    );

    // Calculate today's stats
    const todayWins = todayTrades.filter((t) => t.profit > 0).length;
    const todayPnL = todayTrades.reduce((sum, t) => sum + t.profit, 0);
    const todayWinRate =
      todayTrades.length > 0
        ? Math.round((todayWins / todayTrades.length) * 100)
        : 0;

    // Add open positions P&L
    let openPnL = 0;
    if (positions && Array.isArray(positions)) {
      openPnL = positions.reduce((sum, p) => sum + (p.profit || 0), 0);
    }

    const totalTodayPnL = todayPnL + openPnL;

    // Update DOM
    const resultEl = $id("today-result");
    if (resultEl) {
      resultEl.textContent = `${totalTodayPnL >= 0 ? "+" : ""}$${fmt(totalTodayPnL)}`;
      resultEl.style.color = totalTodayPnL >= 0 ? "var(--green)" : "var(--red)";
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

function updatePositions(positions) {
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
      return `
        <tr>
            <td class="pos-sym">${p.symbol}</td>
            <td class="${tc}">${p.type}</td>
            <td>${p.volume}</td>
            <td>${p.price_open}</td>
            <td>${p.price_current}</td>
            <td>${p.sl || "—"}</td>
            <td>${p.tp || "—"}</td>
            <td class="${pc}">${sign}$${p.profit.toFixed(2)}</td>
            <td><button class="btn-close-pos" onclick="closePosition(${
              p.ticket
            })">Close</button></td>
        </tr>`;
    })
    .join("");

  if (tbody) tbody.innerHTML = fullRows;

  // Dashboard preview: 7 cols (no SL/TP)
  const dashRows = positions
    .map((p) => {
      const tc = p.type === "BUY" ? "pos-buy" : "pos-sell";
      const pc = p.profit >= 0 ? "pos-pos" : "pos-neg";
      const sign = p.profit >= 0 ? "+" : "";
      return `
        <tr>
            <td class="pos-sym">${p.symbol}</td>
            <td class="${tc}">${p.type}</td>
            <td>${p.volume}</td>
            <td>${p.price_open}</td>
            <td>${p.price_current}</td>
            <td class="${pc}">${sign}$${p.profit.toFixed(2)}</td>
            <td style="font-size:10px; color:var(--text-secondary)">${p.sl ? `SL: ${p.sl.toFixed(5)}<br>TP: ${p.tp?.toFixed(5) || "—"}` : "—"}</td>
            <td><button class="btn-close-pos" onclick="closePosition(${
              p.ticket
            })">Close</button></td>
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
  if (!e || e.target === $id("mt5-modal"))
    $id("mt5-modal").classList.remove("show");
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
                <span class="sa-name">${a.name}</span>
                <span class="sa-detail">${a.login || "—"} · ${
                  a.server || "Simulation"
                }</span>
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
  const accounts = await fetch(`${API_BASE}/mt5/saved-accounts`).then((r) =>
    r.json(),
  );
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
  } else {
    icon.textContent = "🔴";
    text.textContent = "Disconnected";
    if (badge) badge.style.display = "none";
  }
}

/* ═══════════════════════════════════════════════════════════
   Manual Trading
   ═══════════════════════════════════════════════════════════ */

function placeOrder(side) {
  const symbol = $id("trade-symbol").value;
  const volume = parseFloat($id("trade-volume").value);
  const sl = parseFloat($id("trade-sl").value) || 0;
  const tp = parseFloat($id("trade-tp").value) || 0;

  if (!volume || volume <= 0) {
    showToast("⚠️ Invalid volume", "error");
    return;
  }

  const price = latestPrices[symbol];
  const priceStr = price ? ` @ ${side === "BUY" ? price.ask : price.bid}` : "";
  if (!confirm(`Place ${side} ${volume} lots ${symbol}${priceStr}?`)) return;

  sendCmd("place_order", {
    symbol,
    order_type: side,
    volume,
    sl,
    tp,
    comment: "Manual",
  });
  showToast(`📤 ${side} order sent: ${volume} ${symbol}`, "info");
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
    const res = await fetch(`${API_BASE}/ai/analyze/EURUSD`, {
      method: "POST",
    });
    const data = await res.json();
    if (data.signal) {
      const conf = data.confidence || 0;
      if (resultEl) {
        resultEl.textContent = `✅ OK — EURUSD: ${data.signal} (${conf}% confidence)`;
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

function closePosition(ticket) {
  if (confirm(`Close position #${ticket}?`))
    sendCmd("close_position", { ticket });
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
    ["mt5-modal", "ai-settings-modal", "retrain-modal"].forEach((id) => {
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

    updateStrategies(strategies);
    updateInsights(insights);

    latestPrices = prices;
    updateTickerBar(prices);
    updateTradePriceDisplay();
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
