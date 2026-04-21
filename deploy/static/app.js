const $ = (sel) => document.querySelector(sel);

const els = {
  scanBtn: $("#scan-now"),
  demoToggle: $("#demo-toggle"),
  minScore: $("#min-score"),
  strongOnly: $("#strong-only"),
  sortBy: $("#sort-by"),
  rows: $("#rows"),
  meta: $("#meta"),
  status: $("#status"),
  error: $("#error"),
  tradesRows: $("#trades-rows"),
  tradesStats: $("#trades-stats"),
  tradeError: $("#trade-error"),
};

const state = {
  signals: [],
  lastScan: null,
  scanAuto: null,
  tradesAuto: null,
  inflight: false,
  trades: { open: [], closed: [], stats: null },
  openingIds: new Set(),
  closingIds: new Set(),
  exchange: "gate",
};

const TRADE_POLL_MS = 5_000;

function fmtPrice(p) {
  if (!Number.isFinite(p)) return "—";
  if (p >= 1) return p.toFixed(4);
  if (p >= 0.01) return p.toFixed(5);
  return p.toExponential(3);
}

function fmtUsd(v) {
  if (!Number.isFinite(v)) return "—";
  const sign = v >= 0 ? "+" : "−";
  return `${sign}$${Math.abs(v).toFixed(2)}`;
}

function fmtPct(v) {
  if (!Number.isFinite(v)) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function fmtAge(iso) {
  if (!iso) return "—";
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function setStatus(kind, text) {
  els.status.className = `status status-${kind}`;
  els.status.textContent = text;
}

function scoreClass(score) {
  if (score >= 85) return "";
  if (score >= 70) return "mid";
  return "low";
}

function sparkSvg(values) {
  if (!values || values.length < 2) return "";
  const w = 96;
  const h = 28;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = w / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / span) * h).toFixed(1)}`)
    .join(" ");
  const up = values[values.length - 1] >= values[0];
  const stroke = up ? "#00ff9d" : "#ff5577";
  return `
    <svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
      <polyline fill="none" stroke="${stroke}" stroke-width="1.5" points="${points}" />
    </svg>`;
}

const BADGE_CLASSES = {
  "Early Pump": "badge-pump",
  "Volume Explosion": "badge-volume",
  Breakout: "badge-breakout",
  Momentum: "badge-momentum",
};

function badgeFor(label) {
  const cls = BADGE_CLASSES[label] || "";
  return `<span class="badge ${cls}">${label}</span>`;
}

function openSymbolIds() {
  return new Set(state.trades.open.map((t) => t.symbol));
}

function renderSignals() {
  const minScore = Math.max(
    Number(els.minScore.value) || 0,
    els.strongOnly.checked ? 80 : 0,
  );
  const key = els.sortBy.value;
  const list = state.signals
    .filter((s) => s.score >= minScore)
    .slice()
    .sort((a, b) => {
      if (key === "symbol") return a.symbol.localeCompare(b.symbol);
      return (b[key] ?? 0) - (a[key] ?? 0);
    });

  if (!list.length) {
    els.rows.innerHTML = `<tr class="empty"><td colspan="8">${
      state.lastScan ? "No signals above threshold right now." : "Waiting for first scan…"
    }</td></tr>`;
    return;
  }

  const hasOpen = openSymbolIds();

  els.rows.innerHTML = list
    .map((s) => {
      const badges = [badgeFor("Early Pump"), ...(s.badges || []).map(badgeFor)].join("");
      const opening = state.openingIds.has(s.symbol);
      const alreadyOpen = hasOpen.has(s.symbol);
      const btnText = opening
        ? "Opening…"
        : alreadyOpen
          ? "Position open"
          : "Trade $100 · 3×";
      const btnClass = `btn-trade${alreadyOpen ? " btn-trade-disabled" : ""}`;
      const disabled = opening || alreadyOpen ? "disabled" : "";
      return `
      <tr>
        <td>
          <div class="symbol">${s.symbol}</div>
          <div class="price">${fmtPrice(s.price)} USDT</div>
        </td>
        <td><div class="badges">${badges}</div></td>
        <td class="num ${s.priceChange >= 0 ? "price-up" : "price-down"}">${fmtPct(s.priceChange)}</td>
        <td class="num">${s.volumeSpike.toFixed(2)}×</td>
        <td class="num"><span class="score-pill ${scoreClass(s.score)}">${s.score}</span></td>
        <td>${sparkSvg(s.sparkline)}</td>
        <td><a class="chart-link" href="${s.chartUrl}" target="_blank" rel="noopener">View chart</a></td>
        <td><button class="${btnClass}" data-symbol="${s.symbol}" data-exchange="${s.exchange || state.exchange}" ${disabled}>${btnText}</button></td>
      </tr>`;
    })
    .join("");
}

async function runScan() {
  if (state.inflight) return;
  state.inflight = true;
  els.scanBtn.disabled = true;
  setStatus("scanning", "scanning…");
  els.error.hidden = true;
  document.body.classList.add("scanning-shimmer");

  try {
    const demo = els.demoToggle.checked ? "1" : "0";
    const res = await fetch(`/signals?demo=${demo}`);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.message || `HTTP ${res.status}`);
    }
    state.signals = data.signals || [];
    state.lastScan = data.scannedAt || new Date().toISOString();
    state.exchange = data.exchange || state.exchange;
    const hitCount = state.signals.length;
    els.meta.textContent = `${hitCount} signal${hitCount === 1 ? "" : "s"} · scanned ${data.scanned ?? 0}/${data.total ?? 0} · ${new Date(state.lastScan).toLocaleTimeString()}${data.demo ? " · DEMO" : ""}`;
    setStatus("ok", data.demo ? "demo" : "live");
    renderSignals();
  } catch (err) {
    setStatus("error", "error");
    els.error.hidden = false;
    els.error.textContent = `Scan failed: ${err.message}. Try enabling Demo mode.`;
  } finally {
    state.inflight = false;
    els.scanBtn.disabled = false;
    document.body.classList.remove("scanning-shimmer");
  }
}

// --------- paper trades ---------

function renderTrades() {
  const { open, closed, stats } = state.trades;
  if (stats) {
    const pnl = stats.totalPnlUsd ?? 0;
    const winRate = stats.closedCount
      ? ` · win ${stats.winCount}/${stats.closedCount} (${stats.winRate}%)`
      : "";
    const pnlText = `${pnl >= 0 ? "+" : "−"}$${Math.abs(pnl).toFixed(2)}`;
    const pnlClass = pnl >= 0 ? "pnl-pos" : "pnl-neg";
    els.tradesStats.innerHTML = `Open ${stats.openCount} · Closed ${stats.closedCount}${winRate} · Cumulative PnL <span class="${pnlClass}">${pnlText}</span>`;
  }

  const rows = [...open, ...closed];
  if (!rows.length) {
    els.tradesRows.innerHTML = `<tr class="empty"><td colspan="8">Click a signal's Trade button to open your first paper position.</td></tr>`;
    return;
  }

  els.tradesRows.innerHTML = rows
    .map((t) => {
      const pnlClass = t.pnlUsd >= 0 ? "price-up" : "price-down";
      const isOpen = t.status === "open";
      const statusBadge = isOpen
        ? `<span class="trade-status open">OPEN · ${t.side.toUpperCase()}</span>`
        : `<span class="trade-status closed close-${t.closeReason}">${(t.closeReason || "closed").toUpperCase()}</span>`;
      const ageIso = isOpen ? t.openedAt : t.closedAt;
      const action = isOpen
        ? `<button class="btn-close" data-id="${t.id}" ${state.closingIds.has(t.id) ? "disabled" : ""}>${state.closingIds.has(t.id) ? "Closing…" : "Close"}</button>`
        : `<span class="muted-small">—</span>`;
      return `
      <tr class="${isOpen ? "" : "trade-row-closed"}">
        <td>
          <div class="symbol">${t.symbol}</div>
          <div class="price">${t.exchange}</div>
        </td>
        <td>${statusBadge}</td>
        <td class="num">${fmtPrice(t.entryPrice)}</td>
        <td class="num">${fmtPrice(t.status === "closed" ? t.closePrice : t.markPrice)}</td>
        <td class="num ${pnlClass}">${fmtUsd(t.pnlUsd)}</td>
        <td class="num ${pnlClass}">${fmtPct(t.pnlPct)}</td>
        <td>${fmtAge(ageIso)}</td>
        <td>${action}</td>
      </tr>`;
    })
    .join("");
}

async function refreshTrades() {
  try {
    const res = await fetch("/api/trades");
    if (!res.ok) return;
    const data = await res.json();
    state.trades = { open: data.open || [], closed: data.closed || [], stats: data.stats };
    renderTrades();
    renderSignals(); // so "Position open" reflects latest state
  } catch {
    // swallow — next tick will retry
  }
}

async function openTrade(symbol, exchange) {
  if (state.openingIds.has(symbol)) return;
  state.openingIds.add(symbol);
  els.tradeError.hidden = true;
  renderSignals();
  try {
    const res = await fetch("/api/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, exchange }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
    state.trades = { open: data.open || [], closed: data.closed || [], stats: data.stats };
    renderTrades();
  } catch (err) {
    els.tradeError.hidden = false;
    els.tradeError.textContent = `Could not open trade for ${symbol}: ${err.message}`;
  } finally {
    state.openingIds.delete(symbol);
    renderSignals();
  }
}

async function closeTrade(id) {
  if (state.closingIds.has(id)) return;
  state.closingIds.add(id);
  renderTrades();
  try {
    const res = await fetch(`/api/trades/${id}/close`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
    state.trades = { open: data.open || [], closed: data.closed || [], stats: data.stats };
  } catch (err) {
    els.tradeError.hidden = false;
    els.tradeError.textContent = `Could not close trade: ${err.message}`;
  } finally {
    state.closingIds.delete(id);
    renderTrades();
    renderSignals();
  }
}

// --------- events ---------

els.scanBtn.addEventListener("click", runScan);
els.demoToggle.addEventListener("change", runScan);
[els.minScore, els.strongOnly, els.sortBy].forEach((el) =>
  el.addEventListener("input", renderSignals),
);

els.rows.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-trade");
  if (!btn || btn.disabled) return;
  openTrade(btn.dataset.symbol, btn.dataset.exchange || state.exchange);
});

els.tradesRows.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-close");
  if (!btn || btn.disabled) return;
  closeTrade(btn.dataset.id);
});

function startAutoRefresh() {
  if (state.scanAuto) clearInterval(state.scanAuto);
  state.scanAuto = setInterval(runScan, 30_000);
  if (state.tradesAuto) clearInterval(state.tradesAuto);
  state.tradesAuto = setInterval(refreshTrades, TRADE_POLL_MS);
}

runScan();
refreshTrades();
startAutoRefresh();
