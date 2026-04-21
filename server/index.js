import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { getExchange } from "./exchanges/index.js";
import { scan } from "./scanner.js";
import { mockScan } from "./mock.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(__dirname, "..", "public");

const PORT = Number(process.env.PORT) || 3000;
const CACHE_TTL_MS = Number(process.env.SIGNALS_CACHE_MS) || 30_000;
const MIN_QUOTE_VOLUME = Number(process.env.MIN_QUOTE_VOLUME) || 5_000_000;
const SYMBOL_LIMIT = Number(process.env.SYMBOL_LIMIT) || 120;
const MIN_SCORE = Number(process.env.MIN_SCORE) || 70;
const DEFAULT_EXCHANGE = process.env.EXCHANGE || "binance";

const app = express();
app.use(express.json());
app.use(express.static(publicDir));

// Simple in-memory cache keyed by exchange. Scans are expensive and rate-limit
// sensitive, so we hand back the same result for CACHE_TTL_MS.
const cache = new Map();
const inflight = new Map();

async function getSignals(exchangeId) {
  const now = Date.now();
  const hit = cache.get(exchangeId);
  if (hit && now - hit.at < CACHE_TTL_MS) return hit.data;

  if (inflight.has(exchangeId)) return inflight.get(exchangeId);

  const exchange = getExchange(exchangeId);
  const p = scan(exchange, {
    minQuoteVolume: MIN_QUOTE_VOLUME,
    symbolLimit: SYMBOL_LIMIT,
    minScore: MIN_SCORE,
  })
    .then((data) => {
      cache.set(exchangeId, { at: Date.now(), data });
      return data;
    })
    .finally(() => inflight.delete(exchangeId));

  inflight.set(exchangeId, p);
  return p;
}

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, exchange: DEFAULT_EXCHANGE });
});

// Main endpoint. Query params:
//   ?demo=1      -> return pre-recorded signals (no network call)
//   ?exchange=gate  (default: binance)
//   ?minScore=80    -> filter in addition to the server minimum
async function handleSignals(req, res) {
  const demo = req.query.demo === "1" || req.query.demo === "true";
  const exchangeId = String(req.query.exchange || DEFAULT_EXCHANGE);
  const minScore = Number(req.query.minScore) || 0;

  try {
    const data = demo ? mockScan(exchangeId) : await getSignals(exchangeId);
    const signals = minScore > 0 ? data.signals.filter((s) => s.score >= minScore) : data.signals;
    res.json({ ...data, signals });
  } catch (err) {
    res.status(502).json({
      error: "scan_failed",
      message: err?.message || String(err),
      hint: "Try demo mode or a different exchange (?exchange=gate).",
    });
  }
}

app.get("/signals", handleSignals);
// /api/signals is an alias so deployers that serve everything under /api/*
// (e.g. Vercel) can hit the same handler without rewrites.
app.get("/api/signals", handleSignals);

app.get("/", (_req, res) => {
  res.sendFile(path.join(publicDir, "index.html"));
});

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`Pump Detector listening on http://localhost:${PORT} (exchange=${DEFAULT_EXCHANGE})`);
});
