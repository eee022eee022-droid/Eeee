// Gate.io public market-data adapter (stub, disabled by default).
// Implements the same shape as binance.js so the scanner can switch sources
// by env var (EXCHANGE=gate). Gate uses "_" in pair names, e.g. BTC_USDT,
// and an interval named "5m". Enable later by wiring into exchanges/index.js.

const BASE = "https://api.gateio.ws/api/v4";

async function getJSON(path) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "User-Agent": "pump-detector/1.0", Accept: "application/json" },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Gate ${path} ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

export async function listActiveUsdtSymbols({ minQuoteVolume = 1_000_000, limit = 120 } = {}) {
  const tickers = await getJSON("/spot/tickers");
  return tickers
    .filter((t) => t.currency_pair.endsWith("_USDT") && Number(t.quote_volume) >= minQuoteVolume)
    .sort((a, b) => Number(b.quote_volume) - Number(a.quote_volume))
    .slice(0, limit)
    .map((t) => t.currency_pair);
}

export async function getKlines(symbol, { interval = "5m", limit = 50 } = {}) {
  // Gate returns [timestamp, volume, close, high, low, open]
  const raw = await getJSON(
    `/spot/candlesticks?currency_pair=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`,
  );
  return raw.map((k) => ({
    openTime: Number(k[0]) * 1000,
    open: Number(k[5]),
    high: Number(k[3]),
    low: Number(k[4]),
    close: Number(k[2]),
    volume: Number(k[1]),
    closeTime: Number(k[0]) * 1000 + 5 * 60 * 1000,
  }));
}

export function chartUrl(symbol) {
  return `https://www.gate.io/trade/${symbol}`;
}

export const gate = {
  id: "gate",
  label: "Gate.io",
  listActiveUsdtSymbols,
  getKlines,
  chartUrl,
};
