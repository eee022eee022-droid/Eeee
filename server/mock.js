// Pre-recorded signals used by /signals?demo=1 so the UI always has something
// to show (useful for deploys where Binance is geo-blocked, e.g. Vercel US).

function spark(base, drift = 0.01, n = 20, seed = 1) {
  const out = [];
  let x = base;
  let s = seed;
  for (let i = 0; i < n; i++) {
    // tiny deterministic "random" walk
    s = (s * 9301 + 49297) % 233280;
    const r = (s / 233280 - 0.4) * drift;
    x = Math.max(0, x * (1 + r + drift * 0.15));
    out.push(Number(x.toFixed(6)));
  }
  return out;
}

const demoSignals = [
  {
    symbol: "DOGEUSDT",
    priceChange: 3.4,
    volumeSpike: 4.2,
    breakout: true,
    bullish: true,
    greenCandles: 4,
    closeNearHigh: 0.94,
    overextended: false,
    earlyPump: true,
    score: 92,
    badges: ["Volume Explosion", "Breakout", "Momentum"],
    price: 0.168,
    sparkline: spark(0.162, 0.012, 20, 11),
    timeframe: "5m",
  },
  {
    symbol: "INJUSDT",
    priceChange: 2.7,
    volumeSpike: 3.1,
    breakout: true,
    bullish: true,
    greenCandles: 3,
    closeNearHigh: 0.88,
    overextended: false,
    earlyPump: true,
    score: 85,
    badges: ["Volume Explosion", "Breakout", "Momentum"],
    price: 25.82,
    sparkline: spark(25.1, 0.009, 20, 23),
    timeframe: "5m",
  },
  {
    symbol: "SEIUSDT",
    priceChange: 2.1,
    volumeSpike: 2.9,
    breakout: true,
    bullish: true,
    greenCandles: 2,
    closeNearHigh: 0.81,
    overextended: false,
    earlyPump: true,
    score: 79,
    badges: ["Volume Explosion", "Breakout"],
    price: 0.412,
    sparkline: spark(0.401, 0.008, 20, 37),
    timeframe: "5m",
  },
  {
    symbol: "PEPEUSDT",
    priceChange: 4.8,
    volumeSpike: 5.7,
    breakout: true,
    bullish: true,
    greenCandles: 5,
    closeNearHigh: 0.97,
    overextended: false,
    earlyPump: true,
    score: 96,
    badges: ["Volume Explosion", "Breakout", "Momentum"],
    price: 0.00000843,
    sparkline: spark(0.00000801, 0.014, 20, 51),
    timeframe: "5m",
  },
  {
    symbol: "TIAUSDT",
    priceChange: 1.9,
    volumeSpike: 2.6,
    breakout: true,
    bullish: true,
    greenCandles: 2,
    closeNearHigh: 0.77,
    overextended: false,
    earlyPump: true,
    score: 74,
    badges: ["Volume Explosion", "Breakout"],
    price: 4.73,
    sparkline: spark(4.64, 0.007, 20, 73),
    timeframe: "5m",
  },
];

export function mockScan(exchangeId = "binance") {
  const binanceChart = (s) => `https://www.binance.com/en/trade/${s.replace("USDT", "_USDT")}?type=spot`;
  const gateChart = (s) => `https://www.gate.io/trade/${s.replace("USDT", "_USDT")}`;
  const chart = exchangeId === "gate" ? gateChart : binanceChart;
  return {
    scannedAt: new Date().toISOString(),
    exchange: exchangeId,
    demo: true,
    scanned: demoSignals.length,
    total: demoSignals.length,
    signals: demoSignals.map((s) => ({
      ...s,
      exchange: exchangeId,
      chartUrl: chart(s.symbol),
    })),
  };
}
