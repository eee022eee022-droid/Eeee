// Core scanner: reads candles, computes indicators and a 0-100 score, and
// returns only early-pump signals. Works with any exchange adapter that
// implements { listActiveUsdtSymbols, getKlines, chartUrl }.

const DEFAULTS = {
  interval: "5m",
  limit: 50,
  minScore: 70,
  priceChangeLookback: 4, // last N closed candles for the "price change" metric
  volumeLookback: 20, // window for average volume comparison
  breakoutLookback: 20, // window for breakout highest-high
  overextendedPct: 10, // already-pumped cutoff (skip signals)
  concurrency: 8, // parallel klines fetches
};

function last(arr, n = 1) {
  return arr[arr.length - n];
}

export function analyze(symbol, candles, cfg = DEFAULTS) {
  if (!candles || candles.length < cfg.breakoutLookback + 2) return null;

  const latest = last(candles);
  const priorClose = last(candles, cfg.priceChangeLookback + 1)?.close ?? candles[0].close;
  const priceChangePct = ((latest.close - priorClose) / priorClose) * 100;

  // Volume spike: latest volume vs average of the previous `volumeLookback`
  const volWindow = candles.slice(-1 - cfg.volumeLookback, -1);
  const avgVolume = volWindow.reduce((s, c) => s + c.volume, 0) / volWindow.length;
  const volumeSpike = avgVolume > 0 ? latest.volume / avgVolume : 0;

  // Breakout: current close strictly above prior window high
  const breakoutWindow = candles.slice(-1 - cfg.breakoutLookback, -1);
  const priorHigh = Math.max(...breakoutWindow.map((c) => c.high));
  const breakout = latest.close > priorHigh;

  // Candle strength: how close the close is to the high of the candle
  const range = latest.high - latest.low;
  const body = latest.close - latest.open;
  const bullish = body > 0;
  const closeNearHigh = range > 0 ? (latest.close - latest.low) / range : 0; // 0..1

  // Momentum: consecutive green closes ending at the latest candle
  let greens = 0;
  for (let i = candles.length - 1; i >= 0; i--) {
    if (candles[i].close > candles[i].open) greens++;
    else break;
  }

  // Already-pumped guard: move over the breakout window is too large
  const lowWindow = Math.min(...breakoutWindow.map((c) => c.low));
  const windowMovePct = lowWindow > 0 ? ((latest.close - lowWindow) / lowWindow) * 100 : 0;
  const overextended = windowMovePct > cfg.overextendedPct * 2 || priceChangePct > cfg.overextendedPct;

  // Scoring (0-100):
  //   price change 0-30 | volume spike 0-30 | breakout 20 | candle strength 10 | momentum 10
  const priceScore = Math.max(0, Math.min(30, (priceChangePct / 5) * 30));
  const volumeScore = Math.max(0, Math.min(30, ((volumeSpike - 1) / 4) * 30));
  const breakoutScore = breakout ? 20 : 0;
  const candleScore = bullish ? Math.round(closeNearHigh * 10) : 0;
  const momentumScore = Math.min(10, Math.max(0, (greens - 1) * 5));

  const score = Math.round(priceScore + volumeScore + breakoutScore + candleScore + momentumScore);

  const earlyPump =
    !overextended &&
    priceChangePct >= 1.5 &&
    volumeSpike >= 2.5 &&
    breakout &&
    bullish;

  // Badges communicate the "why" in the UI
  const badges = [];
  if (volumeSpike >= 2.5) badges.push("Volume Explosion");
  if (breakout) badges.push("Breakout");
  if (greens >= 3) badges.push("Momentum");

  return {
    symbol,
    priceChange: Number(priceChangePct.toFixed(2)),
    volumeSpike: Number(volumeSpike.toFixed(2)),
    breakout,
    bullish,
    greenCandles: greens,
    closeNearHigh: Number(closeNearHigh.toFixed(2)),
    overextended,
    earlyPump,
    score,
    badges,
    price: latest.close,
    sparkline: candles.slice(-20).map((c) => c.close),
    timeframe: cfg.interval,
  };
}

async function runWithConcurrency(items, concurrency, worker) {
  const results = [];
  let i = 0;
  const runners = Array.from({ length: concurrency }, async () => {
    while (i < items.length) {
      const idx = i++;
      try {
        const out = await worker(items[idx], idx);
        if (out) results.push(out);
      } catch {
        // Per-symbol failures are swallowed: one bad klines response shouldn't
        // take down the whole scan.
      }
    }
  });
  await Promise.all(runners);
  return results;
}

export async function scan(exchange, opts = {}) {
  const cfg = { ...DEFAULTS, ...opts };
  const symbols = await exchange.listActiveUsdtSymbols({
    minQuoteVolume: cfg.minQuoteVolume,
    limit: cfg.symbolLimit,
  });

  const analyzed = await runWithConcurrency(symbols, cfg.concurrency, async (symbol) => {
    const candles = await exchange.getKlines(symbol, {
      interval: cfg.interval,
      limit: cfg.limit,
    });
    return analyze(symbol, candles, cfg);
  });

  const signals = analyzed
    .filter((a) => a && a.earlyPump && a.score >= cfg.minScore)
    .sort((a, b) => b.score - a.score)
    .map((a) => ({
      ...a,
      chartUrl: exchange.chartUrl(a.symbol),
      exchange: exchange.id,
    }));

  return {
    scannedAt: new Date().toISOString(),
    exchange: exchange.id,
    scanned: analyzed.length,
    total: symbols.length,
    signals,
  };
}

export { DEFAULTS };
