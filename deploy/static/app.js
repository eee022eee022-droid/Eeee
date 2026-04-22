const $ = (sel) => document.querySelector(sel);

const els = {
  scanBtn: $("#scan-now"),
  minProb: $("#min-prob"),
  tagFilter: $("#tag-filter"),
  autoToggle: $("#auto-toggle"),
  list: $("#prob-list"),
  meta: $("#meta"),
  status: $("#status"),
  error: $("#error"),
  tradesRows: $("#trades-rows"),
  tradesStats: $("#trades-stats"),
  tradeError: $("#trade-error"),
};

const state = {
  top: [],
  lastScan: null,
  scanAuto: null,
  tradesAuto: null,
  inflight: false,
  trades: { open: [], closed: [], stats: null },
  openingIds: new Set(),
  closingIds: new Set(),
  exchange: "gate",
};

const SCAN_INTERVAL_MS = 60_000;
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

function probClass(p) {
  if (p >= 85) return "hot";
  if (p >= 70) return "warm";
  if (p >= 50) return "mid";
  return "low";
}

function sparkSvg(values) {
  if (!values || values.length < 2) return "";
  const w = 120;
  const h = 32;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = w / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / span) * h).toFixed(1)}`)
    .join(" ");
  const up = values[values.length - 1] >= values[0];
  const stroke = up ? "#00ff9d" : "#ff5577";
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <polyline fill="none" stroke="${stroke}" stroke-width="1.5" points="${points}" />
  </svg>`;
}

function openSymbolIds() {
  return new Set(state.trades.open.map((t) => t.symbol));
}

function renderList() {
  const minProb = Number(els.minProb.value) || 0;
  const tag = els.tagFilter.value;
  const rows = state.top.filter(
    (r) => r.probability >= minProb && (!tag || r.tag === tag),
  );

  if (!rows.length) {
    els.list.innerHTML = `<li class="empty">${
      state.lastScan ? "Nothing matches your filters right now." : "Waiting for first scan…"
    }</li>`;
    return;
  }

  const hasOpen = openSymbolIds();

  els.list.innerHTML = rows
    .map((r, i) => {
      const opening = state.openingIds.has(r.symbol);
      const alreadyOpen = hasOpen.has(r.symbol);
      const btnText = opening
        ? "Opening…"
        : alreadyOpen
          ? "Position open"
          : "Trade $100 · 3×";
      const btnClass = `btn-trade${alreadyOpen ? " btn-trade-disabled" : ""}`;
      const disabled = opening || alreadyOpen ? "disabled" : "";
      const reasonBadges = (r.reasons || [])
        .map((t) => `<span class="reason">${t}</span>`)
        .join("");
      const tagHtml = r.tag
        ? `<span class="tag tag-${r.tag.toLowerCase()}">${r.tag}</span>`
        : "";

      return `
      <li class="prob-row prob-${probClass(r.probability)}">
        <div class="rank">${i + 1}</div>
        <div class="info">
          <div class="top-line">
            <span class="symbol">${r.symbol}</span>
            <span class="price">${fmtPrice(r.price)} USDT</span>
            ${tagHtml}
          </div>
          <div class="reasons">${reasonBadges}</div>
        </div>
        <div class="spark-wrap">${sparkSvg(r.sparkline)}</div>
        <div class="prob-pill-wrap">
          <div class="prob-pill">${r.probability}%</div>
          <div class="prob-label">Pump probability</div>
        </div>
        <div class="actions">
          <a class="chart-link" href="${r.chartUrl}" target="_blank" rel="noopener">Chart</a>
          <button class="${btnClass}" data-symbol="${r.symbol}" data-exchange="${r.exchange || state.exchange}" ${disabled}>${btnText}</button>
        </div>
      </li>`;
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
    const res = await fetch(`/api/probability`);
    const data = await res.json();
    if (!res.ok) throw new Error(data?.message || `HTTP ${res.status}`);
    state.top = data.top || [];
    state.lastScan = data.scannedAt || new Date().toISOString();
    state.exchange = data.exchange || state.exchange;
    els.meta.textContent = `Scanned ${data.scanned ?? 0}/${data.total ?? 0} pairs · top ${state.top.length} · ${new Date(state.lastScan).toLocaleTimeString()}`;
    setStatus("ok", "live");
    renderList();
  } catch (err) {
    setStatus("error", "error");
    els.error.hidden = false;
    els.error.textContent = `Scan failed: ${err.message}`;
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
    els.tradesRows.innerHTML = `<tr class="empty"><td colspan="8">Click a row's Trade button to open your first paper position.</td></tr>`;
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
    renderList();
  } catch {
    // swallow
  }
}

async function openTrade(symbol, exchange) {
  if (state.openingIds.has(symbol)) return;
  state.openingIds.add(symbol);
  els.tradeError.hidden = true;
  renderList();
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
    renderList();
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
    renderList();
  }
}

// --------- events ---------

els.scanBtn.addEventListener("click", runScan);
[els.minProb, els.tagFilter].forEach((el) => el.addEventListener("input", renderList));

els.autoToggle.addEventListener("change", () => {
  if (els.autoToggle.checked) startAutoRefresh();
  else stopAutoRefresh();
});

els.list.addEventListener("click", (e) => {
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
  stopAutoRefresh();
  state.scanAuto = setInterval(runScan, SCAN_INTERVAL_MS);
  state.tradesAuto = setInterval(refreshTrades, TRADE_POLL_MS);
}

function stopAutoRefresh() {
  if (state.scanAuto) clearInterval(state.scanAuto);
  if (state.tradesAuto) clearInterval(state.tradesAuto);
  state.scanAuto = null;
  state.tradesAuto = null;
}

runScan();
refreshTrades();
startAutoRefresh();
