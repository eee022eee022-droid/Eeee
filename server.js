const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

const BINANCE_URL = "https://api.binance.com/api/v3/ticker/24hr";
const LEVERAGED_SUFFIXES = ["UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT"];
const MIN_QUOTE_VOLUME = 3_000_000;
const LONG_CHANGE_PCT = 2;
const SHORT_CHANGE_PCT = -2;

function isLeveragedToken(symbol) {
  return LEVERAGED_SUFFIXES.some((suffix) => symbol.endsWith(suffix));
}

function filterTickers(tickers) {
  return tickers
    .filter((t) => typeof t.symbol === "string" && t.symbol.endsWith("USDT"))
    .filter((t) => !isLeveragedToken(t.symbol))
    .map((t) => ({
      symbol: t.symbol,
      lastPrice: parseFloat(t.lastPrice),
      priceChangePercent: parseFloat(t.priceChangePercent),
      quoteVolume: parseFloat(t.quoteVolume),
    }))
    .filter(
      (t) =>
        Number.isFinite(t.lastPrice) &&
        Number.isFinite(t.priceChangePercent) &&
        Number.isFinite(t.quoteVolume) &&
        t.lastPrice > 0 &&
        t.quoteVolume > MIN_QUOTE_VOLUME
    );
}

function round(value, digits = 8) {
  if (!Number.isFinite(value)) return value;
  const factor = Math.pow(10, digits);
  return Math.round(value * factor) / factor;
}

function priceDigits(price) {
  if (price >= 100) return 2;
  if (price >= 1) return 4;
  if (price >= 0.01) return 6;
  return 8;
}

function buildLongIdea(t) {
  const digits = priceDigits(t.lastPrice);
  const entry = round(t.lastPrice, digits);
  const stop = round(t.lastPrice * 0.97, digits);
  const target = round(t.lastPrice * 1.05, digits);
  return {
    symbol: t.symbol,
    side: "LONG",
    lastPrice: entry,
    change24h: round(t.priceChangePercent, 2),
    turnover24h: Math.round(t.quoteVolume),
    entry,
    stop,
    target,
    reason: `Сильный рост за 24ч: +${round(t.priceChangePercent, 2)}% при обороте $${Math.round(
      t.quoteVolume
    ).toLocaleString("en-US")}`,
  };
}

function buildShortIdea(t) {
  const digits = priceDigits(t.lastPrice);
  const entry = round(t.lastPrice, digits);
  const stop = round(t.lastPrice * 1.03, digits);
  const target = round(t.lastPrice * 0.95, digits);
  return {
    symbol: t.symbol,
    side: "SHORT",
    lastPrice: entry,
    change24h: round(t.priceChangePercent, 2),
    turnover24h: Math.round(t.quoteVolume),
    entry,
    stop,
    target,
    reason: `Сильное падение за 24ч: ${round(t.priceChangePercent, 2)}% при обороте $${Math.round(
      t.quoteVolume
    ).toLocaleString("en-US")}`,
  };
}

function selectIdeas(tickers) {
  const longs = tickers
    .filter((t) => t.priceChangePercent > LONG_CHANGE_PCT)
    .sort((a, b) => {
      if (b.priceChangePercent !== a.priceChangePercent) {
        return b.priceChangePercent - a.priceChangePercent;
      }
      return b.quoteVolume - a.quoteVolume;
    })
    .slice(0, 2)
    .map(buildLongIdea);

  const shorts = tickers
    .filter((t) => t.priceChangePercent < SHORT_CHANGE_PCT)
    .sort((a, b) => {
      if (a.priceChangePercent !== b.priceChangePercent) {
        return a.priceChangePercent - b.priceChangePercent;
      }
      return b.quoteVolume - a.quoteVolume;
    })
    .slice(0, 1)
    .map(buildShortIdea);

  return [...longs, ...shorts];
}

async function fetchBinanceTickers() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const res = await fetch(BINANCE_URL, { signal: controller.signal });
    if (!res.ok) {
      throw new Error(`Binance ответил статусом ${res.status}`);
    }
    const data = await res.json();
    if (!Array.isArray(data)) {
      throw new Error("Неожиданный ответ Binance");
    }
    return data;
  } finally {
    clearTimeout(timeout);
  }
}

app.get("/api/ideas", async (_req, res) => {
  try {
    const raw = await fetchBinanceTickers();
    const filtered = filterTickers(raw);
    const ideas = selectIdeas(filtered);
    res.json({
      ok: true,
      updatedAt: new Date().toISOString(),
      ideas,
    });
  } catch (err) {
    console.error("[/api/ideas] error:", err.message);
    res.status(502).json({
      ok: false,
      error: "Не удалось получить данные с Binance. Попробуйте ещё раз через минуту.",
    });
  }
});

app.use(express.static(path.join(__dirname, "public")));

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});
