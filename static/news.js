"use strict";

const POLL_MS = 5000;

const EXCHANGE_LABELS = {
  binance: "Binance",
  okx: "OKX",
  kucoin: "KuCoin",
  kraken: "Kraken",
};

const state = {
  items: [],
  stats: { total: 0, by_exchange: {} },
  serverNow: Date.now(),
  exchange: "",
  q: "",
};

const SYMBOL_RE = /\b[A-Z]{2,10}\b/g;

function fmtAgo(ts) {
  if (!ts) return "—";
  const sec = Math.max(0, Math.floor((state.serverNow - ts) / 1000));
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function fmtAbs(ts) {
  if (!ts) return "unknown";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
}

function extractSymbols(title) {
  const stop = new Set([
    "AND", "THE", "FOR", "WILL", "USD", "ON", "OF", "IN", "AT", "TO", "BY",
    "USDT", "USDC", "EUR", "GBP", "JPY", "BRL", "NEW", "HOT",
    "SPOT", "MARGIN", "FUTURES", "PERPETUAL", "LISTING", "LISTINGS", "TRADING",
    "DELIST", "DELISTING", "REMOVE", "REMOVAL", "SUSPEND", "SUSPENSION",
    "PAIRS", "PAIR", "NOTICE", "UPDATE", "PLAN", "BOT",
    "API", "KYC",
  ]);
  const out = new Set();
  for (const m of title.matchAll(SYMBOL_RE)) {
    const s = m[0];
    if (s.length < 2 || stop.has(s)) continue;
    out.add(s);
  }
  return Array.from(out).slice(0, 8);
}

function renderStats() {
  const box = document.getElementById("stats-cards");
  const by = state.stats.by_exchange || {};
  const pieces = [
    { label: "Total items", value: state.stats.total, sub: "since server start" },
  ];
  for (const ex of Object.keys(EXCHANGE_LABELS)) {
    const info = by[ex] || { count: 0, last_ts: 0 };
    pieces.push({
      label: EXCHANGE_LABELS[ex],
      value: info.count,
      sub: info.last_ts ? `last: ${fmtAgo(info.last_ts)}` : "no items yet",
    });
  }
  box.innerHTML = pieces
    .map(
      (p) => `
    <div class="card">
      <div class="label">${p.label}</div>
      <div class="value">${p.value}</div>
      <div class="sub">${p.sub}</div>
    </div>`
    )
    .join("");
}

function renderExchangeFilter() {
  const wrap = document.getElementById("exchange-filter");
  const exchanges = ["", ...Object.keys(EXCHANGE_LABELS)];
  wrap.innerHTML = exchanges
    .map((ex) => {
      const label = ex === "" ? "All exchanges" : EXCHANGE_LABELS[ex];
      const cls = ex === state.exchange ? "chip active" : "chip";
      return `<button class="${cls}" data-ex="${ex}">${label}</button>`;
    })
    .join("");
  wrap.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.exchange = btn.dataset.ex;
      renderExchangeFilter();
      renderList();
      fetchNews();
    });
  });
}

function renderList() {
  const list = document.getElementById("news-list");
  const q = state.q.trim().toLowerCase();
  const items = state.items.filter((it) => {
    if (q && !it.title.toLowerCase().includes(q)) return false;
    return true;
  });
  document.getElementById("count-label").textContent =
    `${items.length} item${items.length === 1 ? "" : "s"}`;
  document.getElementById("empty").style.display = items.length ? "none" : "block";
  list.innerHTML = items
    .map((it) => {
      const ex = EXCHANGE_LABELS[it.exchange] || it.exchange;
      const syms = extractSymbols(it.title);
      const chips = syms
        .map((s) => `<span class="sym-chip">${s}</span>`)
        .join("");
      return `
        <li class="news-item">
          <div class="news-meta">
            <span class="exchange-tag exchange-${it.exchange}">${ex}</span>
            <span class="muted" title="${fmtAbs(it.published_ts)}">${fmtAgo(it.published_ts)}</span>
          </div>
          <a class="news-title" href="${it.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(it.title)}</a>
          <div class="news-syms">${chips}</div>
        </li>
      `;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function fetchNews() {
  const params = new URLSearchParams({ limit: "200" });
  if (state.exchange) params.set("exchange", state.exchange);
  try {
    const r = await fetch(`/api/news?${params.toString()}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    state.items = d.items || [];
    state.stats = d.stats || { total: 0, by_exchange: {} };
    state.serverNow = d.now_ms || Date.now();
    document.getElementById("status-pill").textContent = "live";
    document.getElementById("status-pill").classList.add("ok");
    document.getElementById("updated-at").textContent = `updated ${fmtAbs(state.serverNow)}`;
    renderStats();
    renderList();
  } catch (e) {
    document.getElementById("status-pill").textContent = "offline";
    document.getElementById("status-pill").classList.remove("ok");
  }
}

function init() {
  renderExchangeFilter();
  document.getElementById("search").addEventListener("input", (e) => {
    state.q = e.target.value;
    renderList();
  });
  fetchNews();
  setInterval(fetchNews, POLL_MS);
  // Relative timestamps drift; re-render every second for the "30s ago" counter.
  setInterval(() => {
    state.serverNow += 1000;
    renderList();
    renderStats();
  }, 1000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
