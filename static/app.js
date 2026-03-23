/* ═══════════════════════════════════════════════════════════
   AI Trading System — Frontend Application
   ═══════════════════════════════════════════════════════════ */

// ─── Configuration ──────────────────────────────────────────

const WS_URL = `ws://${window.location.host}/ws`;
const API_BASE = `http://${window.location.host}/api`;

// ─── State ──────────────────────────────────────────────────

let ws = null;
let systemActive = false;
let reconnectAttempts = 0;
const MAX_RECONNECT = 50;

// ─── DOM Elements ───────────────────────────────────────────

const $id = (id) => document.getElementById(id);

const dom = {
    // Header
    badgeMt5: $id('badge-mt5'),
    btnSystem: $id('btn-system'),
    btnSystemText: $id('btn-system-text'),

    // Cards
    accountBalance: $id('account-balance'),
    winRate: $id('win-rate'),
    strategiesGrid: $id('strategies-grid'),

    // Insights
    mostLostSymbol: $id('most-lost-symbol'),
    weakestAction: $id('weakest-action'),
    totalLossImpact: $id('total-loss-impact'),

    // Positions
    positionsBody: $id('positions-body'),
    noPositions: $id('no-positions'),

    // Modals
    retrainModal: $id('retrain-modal'),
    retrainBody: $id('retrain-body'),
    rankingsModal: $id('rankings-modal'),
    rankingsBody: $id('rankings-body'),

    // Toast
    toastContainer: $id('toast-container'),
};


// ═══ WebSocket ═══════════════════════════════════════════════

function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log('🔗 WebSocket connected');
        reconnectAttempts = 0;
        updateMT5Badge(true);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error('Parse error:', e);
        }
    };

    ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        updateMT5Badge(false);
        scheduleReconnect();
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
    };
}

function scheduleReconnect() {
    if (reconnectAttempts >= MAX_RECONNECT) {
        console.log('Max reconnect attempts reached');
        return;
    }
    reconnectAttempts++;
    const delay = Math.min(2000 * reconnectAttempts, 10000);
    console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts})...`);
    setTimeout(connectWebSocket, delay);
}

function sendCommand(command, data = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command, ...data }));
    }
}


// ═══ Message Handler ═════════════════════════════════════════

function handleMessage(data) {
    switch (data.type) {
        case 'realtime':
            updateDashboard(data);
            break;
        case 'system_toggle':
            systemActive = data.active;
            updateSystemButton();
            showToast(data.active ? '✅ System activated' : '⏸️ System paused', data.active ? 'success' : 'info');
            break;
        case 'strategy_toggle':
            showToast(
                `${data.symbol}: ${data.enabled ? 'ON' : 'OFF'}`,
                data.enabled ? 'success' : 'info'
            );
            break;
        case 'close_result':
            showToast(data.message, data.success ? 'success' : 'error');
            break;
    }
}


// ═══ Dashboard Updates ═══════════════════════════════════════

function updateDashboard(data) {
    // Account
    if (data.account) {
        animateValue(dom.accountBalance, `$${formatNumber(data.account.balance)}`);
    }

    // Win Rate
    if (data.insights) {
        animateValue(dom.winRate, `${data.insights.win_rate}%`);
    }

    // System status
    if (data.status) {
        systemActive = data.status.system_active;
        updateSystemButton();
        updateMT5Badge(data.status.mt5_connected);
    }

    // Strategies
    if (data.strategies) {
        updateStrategies(data.strategies);
    }

    // Insights
    if (data.insights) {
        updateInsights(data.insights);
    }

    // Positions
    if (data.positions !== undefined) {
        updatePositions(data.positions);
    }
}


// ─── Strategies Grid ─────────────────────────────────────────

function updateStrategies(strategies) {
    const grid = dom.strategiesGrid;

    // Only rebuild if different count
    if (grid.children.length !== strategies.length) {
        grid.innerHTML = '';
        strategies.forEach(s => {
            const btn = document.createElement('button');
            btn.className = `strategy-btn ${s.enabled ? 'active' : ''}`;
            btn.id = `strategy-${s.symbol}`;
            btn.onclick = () => toggleStrategy(s.symbol);
            btn.innerHTML = `
                <span class="icon">${s.icon}</span>
                <span class="label">${s.symbol}</span>
                <span class="status">${s.enabled ? 'ON' : 'OFF'}</span>
            `;
            grid.appendChild(btn);
        });
    } else {
        strategies.forEach(s => {
            const btn = $id(`strategy-${s.symbol}`);
            if (btn) {
                const isActive = btn.classList.contains('active');
                if (isActive !== s.enabled) {
                    btn.classList.toggle('active', s.enabled);
                    const statusEl = btn.querySelector('.status');
                    if (statusEl) statusEl.textContent = s.enabled ? 'ON' : 'OFF';
                }
            }
        });
    }
}


// ─── Insights ────────────────────────────────────────────────

function updateInsights(insights) {
    const mostLost = insights.most_lost_symbol;
    dom.mostLostSymbol.textContent = mostLost.symbol || 'None!';

    const weakest = insights.weakest_action;
    dom.weakestAction.textContent = weakest.action || 'Perfect';

    // Color the weakest action based on value
    if (weakest.action === 'Perfect') {
        dom.weakestAction.style.color = 'var(--accent-green)';
    } else {
        dom.weakestAction.style.color = 'var(--accent-orange)';
    }

    dom.totalLossImpact.textContent = `$${formatNumber(insights.total_loss_impact || 0)}`;
}


// ─── Positions Table ─────────────────────────────────────────

function updatePositions(positions) {
    const tbody = dom.positionsBody;
    const noPos = dom.noPositions;

    if (!positions || positions.length === 0) {
        tbody.innerHTML = '';
        noPos.classList.remove('hidden');
        return;
    }

    noPos.classList.add('hidden');

    // Build rows
    const rows = positions.map(p => {
        const typeClass = p.type === 'BUY' ? 'type-buy' : 'type-sell';
        const pnlClass = p.profit >= 0 ? 'pnl-positive' : 'pnl-negative';
        const pnlSign = p.profit >= 0 ? '+' : '';

        return `
            <tr>
                <td><strong>${p.symbol}</strong></td>
                <td class="${typeClass}">${p.type}</td>
                <td>${p.volume}</td>
                <td>${p.price_open}</td>
                <td>${p.price_current}</td>
                <td class="${pnlClass}">${pnlSign}$${p.profit.toFixed(2)}</td>
                <td>
                    <button class="btn-close-position" onclick="closePosition(${p.ticket})">
                        Close
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rows.join('');
}


// ═══ Actions ═════════════════════════════════════════════════

function toggleSystem() {
    sendCommand('toggle_system');
}

function toggleStrategy(symbol) {
    sendCommand('toggle_strategy', { symbol });
}

function closePosition(ticket) {
    if (confirm(`Close position #${ticket}?`)) {
        sendCommand('close_position', { ticket });
    }
}

async function openRetrain() {
    dom.retrainModal.classList.add('show');
    dom.retrainBody.innerHTML = '<div class="loading-spinner"></div><p style="text-align:center">Analyzing performance data...</p>';

    try {
        const res = await fetch(`${API_BASE}/insights/retrain`);
        const data = await res.json();

        if (data.suggestions && data.suggestions.length > 0) {
            dom.retrainBody.innerHTML = data.suggestions.map(s =>
                `<div class="suggestion-item">${s}</div>`
            ).join('');
        } else {
            dom.retrainBody.innerHTML = '<div class="suggestion-item">✅ All systems optimal</div>';
        }
    } catch (e) {
        dom.retrainBody.innerHTML = '<div class="suggestion-item">❌ Failed to fetch suggestions</div>';
    }
}

function closeRetrain(event) {
    if (!event || event.target === dom.retrainModal) {
        dom.retrainModal.classList.remove('show');
    }
}

function closeRankings(event) {
    if (!event || event.target === dom.rankingsModal) {
        dom.rankingsModal.classList.remove('show');
    }
}


// ═══ UI Helpers ══════════════════════════════════════════════

function updateSystemButton() {
    const btn = dom.btnSystem;
    const text = dom.btnSystemText;

    if (systemActive) {
        btn.classList.remove('off');
        text.textContent = 'SYSTEM ON';
    } else {
        btn.classList.add('off');
        text.textContent = 'SYSTEM OFF';
    }
}

function updateMT5Badge(connected) {
    const badge = dom.badgeMt5;
    if (connected) {
        badge.classList.remove('offline');
        badge.querySelector('span:last-child').textContent = 'MT5 Online';
    } else {
        badge.classList.add('offline');
        badge.querySelector('span:last-child').textContent = 'MT5 Offline';
    }
}

function animateValue(el, newValue) {
    if (el.textContent !== newValue) {
        el.style.transition = 'none';
        el.style.opacity = '0.7';
        el.textContent = newValue;
        requestAnimationFrame(() => {
            el.style.transition = 'opacity 0.3s ease';
            el.style.opacity = '1';
        });
    }
}

function formatNumber(num) {
    return Number(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    dom.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 4000);
}


// ═══ Keyboard Shortcuts ═════════════════════════════════════

document.addEventListener('keydown', (e) => {
    // Escape closes modals
    if (e.key === 'Escape') {
        dom.retrainModal.classList.remove('show');
        dom.rankingsModal.classList.remove('show');
    }
    // Space toggles system (when not typing)
    if (e.key === ' ' && e.target === document.body) {
        e.preventDefault();
        toggleSystem();
    }
});


// ═══ Initialize ═════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('🤖 pytradeAI — Dashboard loaded');
    connectWebSocket();

    // Fallback: initial REST fetch
    fetchInitialData();
});

async function fetchInitialData() {
    try {
        const [account, strategies, status, insights] = await Promise.all([
            fetch(`${API_BASE}/account`).then(r => r.json()),
            fetch(`${API_BASE}/strategies`).then(r => r.json()),
            fetch(`${API_BASE}/status`).then(r => r.json()),
            fetch(`${API_BASE}/insights`).then(r => r.json()),
        ]);

        // Account
        dom.accountBalance.textContent = `$${formatNumber(account.balance || 0)}`;

        // Win Rate
        dom.winRate.textContent = `${insights.win_rate || 0}%`;

        // System
        systemActive = status.system_active;
        updateSystemButton();
        updateMT5Badge(status.mt5_connected);

        // Strategies
        updateStrategies(strategies);

        // Insights
        updateInsights(insights);

        console.log('📊 Initial data loaded');
    } catch (e) {
        console.error('Failed to fetch initial data:', e);
        showToast('⚠️ Cannot connect to server', 'error');
    }
}
