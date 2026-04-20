const fmtUsd = (v, digits = 2) =>
  v == null || Number.isNaN(v)
    ? "—"
    : Number(v).toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });

const fmtNum = (v, digits = 4) =>
  v == null || Number.isNaN(v)
    ? "—"
    : Number(v).toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: digits,
      });

const fmtTime = (ms) => {
  if (!ms) return "—";
  const d = new Date(Number(ms));
  return d.toISOString().replace("T", " ").slice(0, 19);
};

const colorClass = (v) =>
  v == null || v === 0 ? "" : v > 0 ? "pos" : "neg";

let equityChart = null;

function renderEquity(points) {
  const ctx = document.getElementById("equity-chart");
  const labels = points.map((p) => new Date(p.ts));
  const equity = points.map((p) => p.equity_usdt);
  if (!equityChart) {
    equityChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Equity (USDT)",
            data: equity,
            borderColor: "#5eead4",
            backgroundColor: "rgba(94, 234, 212, 0.12)",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        animation: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            type: "time",
            time: { unit: "minute" },
            ticks: { color: "#7d8ab8", maxTicksLimit: 8 },
            grid: { color: "rgba(255,255,255,0.04)" },
          },
          y: {
            ticks: { color: "#7d8ab8" },
            grid: { color: "rgba(255,255,255,0.06)" },
          },
        },
      },
    });
  } else {
    equityChart.data.labels = labels;
    equityChart.data.datasets[0].data = equity;
    equityChart.update("none");
  }
  const range = document.getElementById("equity-range");
  if (points.length > 1) {
    range.textContent = `${fmtTime(points[0].ts)}  →  ${fmtTime(
      points[points.length - 1].ts
    )}`;
  } else {
    range.textContent = "collecting…";
  }
}

function renderMarkets(prices, strategy) {
  const tbody = document.querySelector("#markets-tbl tbody");
  const rows = [];
  const symbols = Object.keys(strategy || {});
  for (const sym of symbols) {
    const s = strategy[sym] || {};
    const px = prices[sym]?.price ?? s.last_price;
    const atrPct =
      s.atr != null && px ? ((s.atr / px) * 100).toFixed(3) : "—";
    rows.push(`
      <tr>
        <td><b>${sym}</b></td>
        <td>${fmtNum(px, 4)}</td>
        <td>${fmtNum(s.ema_fast, 4)} / ${fmtNum(s.ema_slow, 4)}</td>
        <td>${fmtNum(s.rsi, 1)}</td>
        <td>${atrPct}</td>
        <td>${s.ready ? "✔" : `warmup ${s.bars_seen || 0}`}</td>
      </tr>`);
  }
  tbody.innerHTML = rows.join("");
}

function renderPositions(positions) {
  const tbody = document.querySelector("#positions-tbl tbody");
  if (!positions || positions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="muted">no open positions</td></tr>`;
    return;
  }
  tbody.innerHTML = positions
    .map(
      (p) => `
    <tr>
      <td><b>${p.symbol}</b></td>
      <td>${fmtNum(p.qty, 6)}</td>
      <td>${fmtNum(p.entry_price, 4)}</td>
      <td>${fmtNum(p.last_mark, 4)}</td>
      <td>${fmtNum(p.stop_price, 4)}</td>
      <td>${fmtNum(p.target_price, 4)}</td>
      <td class="${colorClass(p.unrealized_pnl)}">${fmtUsd(
        p.unrealized_pnl,
        4
      )}</td>
    </tr>`
    )
    .join("");
}

function renderTrades(trades) {
  const tbody = document.querySelector("#trades-tbl tbody");
  if (!trades || trades.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="muted">no trades yet — waiting for a valid signal</td></tr>`;
    return;
  }
  tbody.innerHTML = trades
    .map(
      (t) => `
    <tr>
      <td>${fmtTime(t.closed_ts)}</td>
      <td><b>${t.symbol}</b></td>
      <td>${fmtNum(t.qty, 6)}</td>
      <td>${fmtNum(t.entry_price, 4)}</td>
      <td>${fmtNum(t.exit_price, 4)}</td>
      <td>${t.exit_reason || ""}</td>
      <td class="${colorClass(t.pnl_usdt)}">${fmtUsd(t.pnl_usdt, 4)}</td>
    </tr>`
    )
    .join("");
}

async function tick() {
  try {
    const [stateRes, tradesRes, equityRes] = await Promise.all([
      fetch("/api/state"),
      fetch("/api/trades?limit=50"),
      fetch("/api/equity?limit=480"),
    ]);
    if (!stateRes.ok) throw new Error(`state ${stateRes.status}`);
    const state = await stateRes.json();
    const trades = (await tradesRes.json()).trades || [];
    const equity = (await equityRes.json()).equity || [];

    const acct = state.account || {};
    document.getElementById("equity").textContent = fmtUsd(acct.equity_usdt);
    const retEl = document.getElementById("return-pct");
    retEl.textContent = `${(state.return_pct || 0).toFixed(2)}% since start`;
    retEl.className = "sub " + colorClass(state.return_pct || 0);

    document.getElementById("balance").textContent = fmtUsd(acct.balance_usdt);
    document.getElementById("initial").textContent =
      `initial ${fmtUsd(acct.initial_balance_usdt)} USDT`;

    const openPnlEl = document.getElementById("open-pnl");
    openPnlEl.textContent = fmtUsd(acct.open_pnl_usdt, 4);
    openPnlEl.className = "value " + colorClass(acct.open_pnl_usdt);
    document.getElementById("open-count").textContent = `${
      (acct.open_positions || []).length
    } open position(s)`;

    const realized = state.stats?.realized_pnl_usdt || 0;
    const realEl = document.getElementById("realized");
    realEl.textContent = fmtUsd(realized, 4);
    realEl.className = "value " + colorClass(realized);
    document.getElementById(
      "winrate"
    ).textContent = `${state.stats?.closed_trades || 0} closed, win ${(
      (state.stats?.win_rate || 0) * 100
    ).toFixed(1)}%`;

    document.getElementById("now").textContent = fmtTime(state.now_ms);
    document.getElementById("status-pill").textContent = "live";
    document.getElementById("live-dot").classList.add("live");
    document.getElementById("live-dot").classList.remove("down");

    const cfg = state.config || {};
    document.getElementById("cfg").textContent = `EMA ${cfg.ema_fast}/${
      cfg.ema_slow
    } · RSI(${cfg.rsi_period}) · ATR stop×${cfg.atr_stop_mult} / target×${
      cfg.atr_target_mult
    } · risk ${(cfg.risk_per_trade * 100).toFixed(2)}% · max pos ${
      cfg.max_open_positions
    } · fee ${(cfg.taker_fee * 100).toFixed(2)}%`;

    renderMarkets(state.prices || {}, state.strategy || {});
    renderPositions(acct.open_positions || []);
    renderTrades(trades);
    if (equity.length > 0) renderEquity(equity);
  } catch (e) {
    document.getElementById("status-pill").textContent = "offline";
    document.getElementById("live-dot").classList.remove("live");
    document.getElementById("live-dot").classList.add("down");
    console.warn("tick error", e);
  }
}

document.getElementById("close-all").addEventListener("click", async () => {
  if (!confirm("Close all open positions at market?")) return;
  const r = await fetch("/api/close-all", { method: "POST" });
  if (!r.ok) alert("Failed to close positions");
  tick();
});

tick();
setInterval(tick, 2000);
