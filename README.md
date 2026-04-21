# Что купить сейчас · Binance scanner

Простой crypto scanner на Node.js + Express. Берёт 24h тикеры с Binance и
показывает 1–3 идеи: что купить (LONG) или шортить (SHORT) сейчас.

## Запуск

```bash
npm install
npm start
```

Затем откройте http://localhost:3000

Порт настраивается через `PORT` (по умолчанию 3000).

## API

- `GET /api/ideas` — возвращает `{ ok, updatedAt, ideas: [...] }`

## Логика фильтра

- Только пары `*USDT`
- Исключены leveraged tokens: `*UPUSDT`, `*DOWNUSDT`, `*BULLUSDT`, `*BEARUSDT`
- `quoteVolume > 3_000_000`
- `lastPrice > 0`

Сигналы:
- LONG: рост 24ч > +2%, топ-2 по росту
- SHORT: падение 24ч < -2%, топ-1 по падению

Не финансовая рекомендация.
