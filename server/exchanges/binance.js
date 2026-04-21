// Binance public market-data adapter.
// Exchange adapters expose a uniform shape so the scanner can later support
// Gate, Bybit, OKX, etc. without touching scanner/core logic.

const BASE = "https://api.binance.com";

async function getJSON(path) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { "User-Agent": "pump-detector/1.0" },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Binance ${path} ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// Returns the list of USDT spot symbols worth scanning:
//  - status TRADING
//  - quote asset USDT
//  - not a leveraged token (UP/DOWN/BULL/BEAR)
//  - quote volume over `minQuoteVolume` USDT in the last 24h
export async function listActiveUsdtSymbols({ minQuoteVolume = 5_000_000, limit = 120 } = {}) {
  const [info, tickers] = await Promise.all([
    getJSON("/api/v3/exchangeInfo"),
    getJSON("/api/v3/ticker/24hr"),
  ]);

  const tradable = new Set(
    info.symbols
      .filter(
        (s) =>
          s.status === "TRADING" &&
          s.quoteAsset === "USDT" &&
          s.isSpotTradingAllowed &&
          !/(UP|DOWN|BULL|BEAR)USDT$/.test(s.symbol),
      )
      .map((s) => s.symbol),
  );

  return tickers
    .filter((t) => tradable.has(t.symbol) && Number(t.quoteVolume) >= minQuoteVolume)
    .sort((a, b) => Number(b.quoteVolume) - Number(a.quoteVolume))
    .slice(0, limit)
    .map((t) => t.symbol);
}

// Returns normalized klines: [{ openTime, open, high, low, close, volume, closeTime }]
export async function getKlines(symbol, { interval = "5m", limit = 50 } = {}) {
  const raw = await getJSON(
    `/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`,
  );
  return raw.map((k) => ({
    openTime: k[0],
    open: Number(k[1]),
    high: Number(k[2]),
    low: Number(k[3]),
    close: Number(k[4]),
    volume: Number(k[5]),
    closeTime: k[6],
  }));
}

export function chartUrl(symbol) {
  return `https://www.binance.com/en/trade/${symbol.replace("USDT", "_USDT")}?type=spot`;
}

export const binance = {
  id: "binance",
  label: "Binance",
  listActiveUsdtSymbols,
  getKlines,
  chartUrl,
};
