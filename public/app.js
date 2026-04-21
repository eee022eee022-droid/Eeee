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
};

const state = {
  signals: [],
  lastScan: null,
  auto: null,
  inflight: false,
};

function fmtPrice(p) {
  if (!Number.isFinite(p)) return "—";
  if (p >= 1) return p.toFixed(4);
  if (p >= 0.01) return p.toFixed(5);
  return p.toExponential(3);
}

function fmtPct(v) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
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

function render() {
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
    els.rows.innerHTML = `<tr class="empty"><td colspan="7">${
      state.lastScan ? "No signals above threshold right now." : "Waiting for first scan…"
    }</td></tr>`;
    return;
  }

  els.rows.innerHTML = list
    .map((s) => {
      const badges = [badgeFor("Early Pump"), ...(s.badges || []).map(badgeFor)].join("");
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
    const hitCount = state.signals.length;
    els.meta.textContent = `${hitCount} signal${hitCount === 1 ? "" : "s"} · scanned ${data.scanned ?? 0}/${data.total ?? 0} · ${new Date(state.lastScan).toLocaleTimeString()}${data.demo ? " · DEMO" : ""}`;
    setStatus("ok", data.demo ? "demo" : "live");
    render();
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

function startAutoRefresh() {
  if (state.auto) clearInterval(state.auto);
  state.auto = setInterval(runScan, 30_000);
}

els.scanBtn.addEventListener("click", runScan);
els.demoToggle.addEventListener("change", runScan);
[els.minScore, els.strongOnly, els.sortBy].forEach((el) =>
  el.addEventListener("input", render),
);

runScan();
startAutoRefresh();
