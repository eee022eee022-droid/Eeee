import { binance } from "./binance.js";
import { gate } from "./gate.js";

const registry = {
  binance,
  gate,
};

export function getExchange(id = process.env.EXCHANGE || "binance") {
  const exchange = registry[id];
  if (!exchange) {
    throw new Error(`Unknown exchange "${id}". Available: ${Object.keys(registry).join(", ")}`);
  }
  return exchange;
}
