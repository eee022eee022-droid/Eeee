import { useState } from 'react'

const ALIEXPRESS_URL =
  'https://aliexpress.ru/wholesale?SearchText=wearable+heated+blanket+hoodie+cordless+battery'
const ALIEXPRESS_BACKUP =
  'https://www.aliexpress.com/w/wholesale-wearable-heated-blanket-hoodie.html'
const TELEGRAM_URL = 'https://t.me/'

const HERO_IMAGE =
  'https://images.unsplash.com/photo-1508898578281-774ac4893c0c?auto=format&fit=crop&w=1400&q=80'
const LIFESTYLE_1 =
  'https://images.unsplash.com/photo-1544441892-794166f1e3be?auto=format&fit=crop&w=900&q=80'
const LIFESTYLE_2 =
  'https://images.unsplash.com/photo-1545194445-dddb8f4487c6?auto=format&fit=crop&w=900&q=80'
const LIFESTYLE_3 =
  'https://images.unsplash.com/photo-1449247709967-d4461a6a6103?auto=format&fit=crop&w=1200&q=80'

type ColorOption = { id: string; label: string; swatch: string }
const COLORS: ColorOption[] = [
  { id: 'latte', label: 'Латте', swatch: '#D9B99B' },
  { id: 'rose', label: 'Пыльная роза', swatch: '#E9B8A8' },
  { id: 'cocoa', label: 'Какао', swatch: '#6B4435' },
]

const FEATURES: { emoji: string; title: string; text: string }[] = [
  {
    emoji: '🔋',
    title: 'До 10 часов тепла',
    text: 'Съёмный аккумулятор 10 000 мАч. Заряжается через USB-C за 2,5 часа.',
  },
  {
    emoji: '🔥',
    title: '3 уровня нагрева',
    text: 'Быстрый прогрев за 30 секунд. Автоотключение через 8 часов.',
  },
  {
    emoji: '🧸',
    title: 'Двойной плюш шерпа',
    text: 'Внешний флис + внутренняя шерпа. Обнимает как облако.',
  },
  {
    emoji: '🧺',
    title: 'Стирается в машинке',
    text: 'Достаёшь нагревательный модуль — стираешь как обычный плед.',
  },
  {
    emoji: '📍',
    title: '4 зоны подогрева',
    text: 'Грудь, поясница, живот и спина. Равномерное тепло, а не точки.',
  },
  {
    emoji: '✈️',
    title: 'Берёшь куда угодно',
    text: 'Работает без розетки. Дом, дача, стадион, машина, самолёт.',
  },
]

const FAQ: { q: string; a: string }[] = [
  {
    q: 'Сколько идёт доставка в Россию?',
    a: 'Через AliExpress — в среднем 10–20 дней до Москвы и Санкт-Петербурга, 14–25 дней в регионы. Отслеживание по трек-номеру.',
  },
  {
    q: 'Безопасно ли спать в таком худи?',
    a: 'Да. Встроенный термостат NTC держит температуру не выше +55 °C и автоматически отключается через 8 часов, но для сна мы всё же рекомендуем выключать нагрев.',
  },
  {
    q: 'Можно ли стирать?',
    a: 'Да. Вытаскиваешь аккумулятор и нагревательный модуль через карман — стираешь в стиральной машине при 30 °C.',
  },
  {
    q: 'Подойдёт ли размер?',
    a: 'Oversize-крой, универсальный размер. Подходит на рост 150–190 см и до 52-го размера включительно.',
  },
  {
    q: 'Есть гарантия?',
    a: 'Да, 12 месяцев от продавца на AliExpress + встроенная защита покупателя AliExpress (возврат при браке).',
  },
]

function App() {
  const [activeColor, setActiveColor] = useState(COLORS[0].id)
  const [faqOpen, setFaqOpen] = useState<number | null>(0)

  return (
    <div className="min-h-screen bg-cream text-charcoal">
      {/* NAV */}
      <header className="sticky top-0 z-40 backdrop-blur bg-cream/80 border-b border-sand">
        <div className="mx-auto max-w-6xl px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🧣</span>
            <span className="font-display text-lg font-bold tracking-tight">
              CozyHood
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium">
            <a href="#product" className="hover:text-clay">
              Продукт
            </a>
            <a href="#features" className="hover:text-clay">
              Как работает
            </a>
            <a href="#faq" className="hover:text-clay">
              Вопросы
            </a>
          </nav>
          <a
            href={ALIEXPRESS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden md:inline-flex items-center gap-2 rounded-full bg-cocoa text-cream px-5 py-2.5 text-sm font-semibold hover:bg-charcoal transition"
          >
            Заказать →
          </a>
        </div>
      </header>

      {/* HERO */}
      <section className="mx-auto max-w-6xl px-5 pt-10 pb-16 md:pt-16 md:pb-24 grid md:grid-cols-2 gap-10 items-center">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-rose/40 text-cocoa px-3 py-1 text-xs font-semibold uppercase tracking-wider">
            Новинка из Китая · Нет на WB и Ozon
          </span>
          <h1 className="font-display text-4xl md:text-6xl font-bold leading-[1.05] mt-5">
            Худи-плед,
            <br />
            которое <span className="text-clay">греет само</span>.
          </h1>
          <p className="mt-6 text-lg md:text-xl text-cocoa/80 max-w-xl">
            CozyHood — беспроводное электро-одеяло нового поколения.
            Надел, включил, и 10 часов тебе тепло. Без розетки, без проводов,
            без котёнка под боком (хотя котёнок не помешает).
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <div>
              <div className="text-xs uppercase tracking-wider text-cocoa/60">
                Цена с доставкой
              </div>
              <div className="flex items-baseline gap-3">
                <span className="font-display text-3xl md:text-4xl font-bold">
                  4 990 ₽
                </span>
                <span className="text-cocoa/50 line-through text-lg">
                  7 490 ₽
                </span>
              </div>
            </div>
            <a
              href={ALIEXPRESS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full bg-clay text-cream px-7 py-4 text-base font-semibold shadow-soft hover:bg-cocoa transition"
            >
              Купить на AliExpress →
            </a>
          </div>

          <div className="mt-5 flex items-center gap-4 text-sm text-cocoa/70">
            <span className="flex items-center gap-1">
              <span>⭐️⭐️⭐️⭐️⭐️</span>
              <span className="font-medium">4.8/5</span>
            </span>
            <span>·</span>
            <span>14 000+ заказов</span>
            <span>·</span>
            <span>Доставка 10–20 дней</span>
          </div>
        </div>

        <div className="relative">
          <div className="absolute -inset-6 bg-rose/30 rounded-[40px] blur-2xl" />
          <div className="relative rounded-[32px] overflow-hidden shadow-soft border-4 border-white">
            <img
              src={HERO_IMAGE}
              alt="CozyHood худи-плед"
              className="w-full h-[420px] md:h-[520px] object-cover"
            />
          </div>
          <div className="absolute -bottom-5 -left-5 bg-white rounded-2xl shadow-soft px-4 py-3 flex items-center gap-3">
            <span className="text-2xl">🔥</span>
            <div>
              <div className="text-xs text-cocoa/60">Температура</div>
              <div className="font-semibold">35° · 45° · 55°</div>
            </div>
          </div>
          <div className="absolute -top-4 -right-4 bg-cocoa text-cream rounded-full px-4 py-2 text-xs font-bold rotate-6 shadow-soft">
            −33% сегодня
          </div>
        </div>
      </section>

      {/* SOCIAL PROOF BAR */}
      <section className="bg-sand/60 border-y border-sand">
        <div className="mx-auto max-w-6xl px-5 py-6 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          <Stat value="10 ч" label="автономной работы" />
          <Stat value="55°" label="максимальный нагрев" />
          <Stat value="4" label="зоны подогрева" />
          <Stat value="−33%" label="скидка по промо" />
        </div>
      </section>

      {/* PRODUCT SELECTOR */}
      <section id="product" className="mx-auto max-w-6xl px-5 py-16 md:py-24">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div className="order-2 md:order-1">
            <h2 className="font-display text-3xl md:text-5xl font-bold">
              Три цвета, один oversize
            </h2>
            <p className="mt-4 text-cocoa/80 text-lg">
              Универсальный размер — подойдёт и подруге, и маме, и тебе.
              Oversize-крой, глубокий капюшон, передний карман-муфта.
            </p>

            <div className="mt-8">
              <div className="text-sm font-semibold uppercase tracking-wider text-cocoa/60 mb-3">
                Выбери цвет
              </div>
              <div className="flex gap-4">
                {COLORS.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setActiveColor(c.id)}
                    className={`flex flex-col items-center gap-2 group`}
                  >
                    <span
                      className={`block w-12 h-12 rounded-full border-4 transition ${
                        activeColor === c.id
                          ? 'border-cocoa scale-110'
                          : 'border-white group-hover:border-sand'
                      }`}
                      style={{ background: c.swatch }}
                    />
                    <span
                      className={`text-xs font-medium ${
                        activeColor === c.id ? 'text-cocoa' : 'text-cocoa/60'
                      }`}
                    >
                      {c.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <ul className="mt-8 space-y-3 text-cocoa/80">
              <Check>Аккумулятор 10 000 мАч в комплекте</Check>
              <Check>Кабель USB-C + инструкция на русском</Check>
              <Check>Размер 140×90 см, универсальный oversize</Check>
              <Check>Подходит мужчинам и женщинам</Check>
            </ul>

            <a
              href={ALIEXPRESS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-10 inline-flex items-center gap-2 rounded-full bg-cocoa text-cream px-7 py-4 text-base font-semibold shadow-soft hover:bg-charcoal transition"
            >
              Заказать в цвете «{COLORS.find((c) => c.id === activeColor)?.label}» →
            </a>
          </div>

          <div className="order-1 md:order-2 grid grid-cols-2 gap-4">
            <img
              src={LIFESTYLE_1}
              alt=""
              className="rounded-3xl object-cover h-48 md:h-64 w-full shadow-soft"
            />
            <img
              src={LIFESTYLE_2}
              alt=""
              className="rounded-3xl object-cover h-48 md:h-64 w-full shadow-soft mt-8"
            />
            <img
              src={LIFESTYLE_3}
              alt=""
              className="rounded-3xl object-cover h-48 md:h-64 w-full shadow-soft col-span-2"
            />
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="bg-white/60 border-y border-sand">
        <div className="mx-auto max-w-6xl px-5 py-16 md:py-24">
          <div className="text-center max-w-2xl mx-auto">
            <h2 className="font-display text-3xl md:text-5xl font-bold">
              Почему CozyHood, а не обычный плед
            </h2>
            <p className="mt-4 text-cocoa/80 text-lg">
              Это не грелка и не электроплед, которые жрут розетку. Это гибрид:
              худи + плед + встроенный обогреватель на аккумуляторе.
            </p>
          </div>

          <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="bg-cream rounded-3xl p-6 border border-sand hover:border-clay transition"
              >
                <div className="text-3xl">{f.emoji}</div>
                <h3 className="mt-4 font-display font-bold text-xl">{f.title}</h3>
                <p className="mt-2 text-cocoa/70 leading-relaxed">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="mx-auto max-w-6xl px-5 py-16 md:py-24">
        <h2 className="font-display text-3xl md:text-5xl font-bold text-center">
          Как заказать
        </h2>
        <div className="mt-12 grid md:grid-cols-3 gap-6">
          <Step n={1} title="Нажми «Купить»" text="Перейдёшь на карточку товара на AliExpress с доставкой в Россию." />
          <Step n={2} title="Оплати любой картой" text="Мир, UnionPay, СБП. AliExpress принимает российские карты." />
          <Step n={3} title="Получи через 10–20 дней" text="Трек-номер придёт в приложение AliExpress. Забираешь в ПВЗ." />
        </div>
        <div className="mt-12 text-center">
          <a
            href={ALIEXPRESS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-clay text-cream px-8 py-4 text-lg font-semibold shadow-soft hover:bg-cocoa transition"
          >
            Заказать с доставкой в Россию →
          </a>
          <div className="mt-3 text-sm text-cocoa/60">
            Если ссылка не открывается —{' '}
            <a
              href={ALIEXPRESS_BACKUP}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              запасная ссылка
            </a>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-sand/40 border-t border-sand">
        <div className="mx-auto max-w-3xl px-5 py-16 md:py-24">
          <h2 className="font-display text-3xl md:text-5xl font-bold text-center">
            Частые вопросы
          </h2>
          <div className="mt-10 space-y-3">
            {FAQ.map((item, i) => (
              <div
                key={item.q}
                className="bg-cream rounded-2xl border border-sand overflow-hidden"
              >
                <button
                  onClick={() => setFaqOpen(faqOpen === i ? null : i)}
                  className="w-full text-left px-5 py-4 flex justify-between items-center gap-4"
                >
                  <span className="font-semibold">{item.q}</span>
                  <span
                    className={`text-xl transition-transform ${
                      faqOpen === i ? 'rotate-45' : ''
                    }`}
                  >
                    +
                  </span>
                </button>
                {faqOpen === i && (
                  <div className="px-5 pb-5 text-cocoa/80 leading-relaxed">
                    {item.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="mx-auto max-w-6xl px-5 py-20 md:py-28">
        <div className="bg-cocoa text-cream rounded-[40px] p-10 md:p-16 text-center relative overflow-hidden">
          <div className="absolute -top-10 -right-10 w-40 h-40 bg-clay/40 rounded-full blur-3xl" />
          <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-rose/30 rounded-full blur-3xl" />
          <div className="relative">
            <h2 className="font-display text-3xl md:text-5xl font-bold">
              Зима длиной в 7 месяцев.
              <br />
              Пора одеться правильно.
            </h2>
            <p className="mt-5 text-cream/80 text-lg max-w-xl mx-auto">
              Сегодня −33% по промо. Завтра — обычная цена 7 490 ₽.
            </p>
            <a
              href={ALIEXPRESS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-flex items-center gap-2 rounded-full bg-cream text-cocoa px-8 py-4 text-lg font-bold hover:bg-rose transition"
            >
              Забрать за 4 990 ₽ →
            </a>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-sand">
        <div className="mx-auto max-w-6xl px-5 py-8 flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-cocoa/60">
          <div className="flex items-center gap-2">
            <span>🧣</span>
            <span className="font-display font-bold text-cocoa">CozyHood</span>
            <span>· {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-6">
            <a href={ALIEXPRESS_URL} target="_blank" rel="noopener noreferrer" className="hover:text-cocoa">
              AliExpress
            </a>
            <a href={TELEGRAM_URL} target="_blank" rel="noopener noreferrer" className="hover:text-cocoa">
              Telegram
            </a>
            <a href="#faq" className="hover:text-cocoa">
              Вопросы
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-display text-3xl md:text-4xl font-bold text-cocoa">
        {value}
      </div>
      <div className="text-xs md:text-sm text-cocoa/60 uppercase tracking-wider mt-1">
        {label}
      </div>
    </div>
  )
}

function Check({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-1 inline-flex items-center justify-center w-5 h-5 rounded-full bg-clay text-cream text-xs font-bold shrink-0">
        ✓
      </span>
      <span>{children}</span>
    </li>
  )
}

function Step({ n, title, text }: { n: number; title: string; text: string }) {
  return (
    <div className="bg-cream border border-sand rounded-3xl p-6">
      <div className="w-12 h-12 rounded-full bg-cocoa text-cream flex items-center justify-center font-display text-xl font-bold">
        {n}
      </div>
      <h3 className="mt-5 font-display font-bold text-xl">{title}</h3>
      <p className="mt-2 text-cocoa/70 leading-relaxed">{text}</p>
    </div>
  )
}

export default App
