import { useState } from 'react'

const ALIEXPRESS_URL =
  'https://aliexpress.ru/wholesale?SearchText=heated+brow+lamination+comb+eyebrow+styling'
const ALIEXPRESS_BACKUP =
  'https://www.aliexpress.com/w/wholesale-electric-eyebrow-styling-comb.html'
const WHOLESALE_1688_URL =
  'https://s.1688.com/selloffer/offer_search.htm?keywords=%E7%9C%89%E6%AF%9B%E5%AE%9A%E5%9E%8B%E6%A2%B3'
const TELEGRAM_URL = 'https://t.me/'

type ColorOption = { id: string; label: string; swatch: string }
const COLORS: ColorOption[] = [
  { id: 'rose', label: 'Пыльная роза', swatch: '#E9B8A8' },
  { id: 'pearl', label: 'Жемчуг', swatch: '#F3EDE4' },
  { id: 'mint', label: 'Мята', swatch: '#BFD8C9' },
]

const FEATURES: { emoji: string; title: string; text: string }[] = [
  {
    emoji: '⚡️',
    title: 'Эффект за 90 секунд',
    text: 'Прогреваешь брови расчёской — волоски встают вверх и фиксируются в нужном направлении.',
  },
  {
    emoji: '📅',
    title: 'Держится до 24 часов',
    text: 'На сухую — на весь день. С фиксирующим гелем — до 2 суток, пережив душ и спорт.',
  },
  {
    emoji: '🌡',
    title: '45 °C — не обжигает',
    text: 'Встроенный термостат держит ровную температуру. Кожа и волоски в безопасности.',
  },
  {
    emoji: '🔌',
    title: 'USB-C, 60 минут работы',
    text: 'Заряжается от любой зарядки телефона. Хватает на 2 недели ежедневного использования.',
  },
  {
    emoji: '👁',
    title: 'Ресницы — в комплекте',
    text: 'Сменная силиконовая насадка подкручивает ресницы. 2 прибора в одном.',
  },
  {
    emoji: '💼',
    title: 'Помещается в косметичку',
    text: 'Размер с тюбик туши — 12×2 см. Берёшь с собой, в самолёт проносится.',
  },
]

const COMPARE: { label: string; salon: string; device: string }[] = [
  { label: 'Цена', salon: 'от 3 500 ₽', device: '1 490 ₽ один раз' },
  { label: 'Время', salon: '45–60 мин в салоне', device: '90 секунд дома' },
  { label: 'Частота', salon: '1 раз в 6–8 недель', device: 'каждое утро' },
  { label: 'Химия', salon: 'тиогликолят + краска', device: 'только тепло' },
  { label: 'Запись', salon: 'за 2 недели', device: 'прямо сейчас' },
]

const FAQ: { q: string; a: string }[] = [
  {
    q: 'Это правда заменяет ламинирование в салоне?',
    a: 'Да — визуально. В салоне эффект держится 6–8 недель за счёт химического состава, дома — сутки за счёт нагрева. Но салон стоит 3 500 ₽ за процедуру, а прибор окупается после первого месяца.',
  },
  {
    q: 'Безопасно ли для кожи и волосков?',
    a: 'Температура 45 °C — ниже чем у утюжка для волос (150–200 °C). Встроенный термостат NTC не даёт перегреть. Волоски не сжигаются и не ломаются.',
  },
  {
    q: 'Сколько идёт доставка?',
    a: 'AliExpress в Россию — 10–20 дней до Москвы и СПб, 14–25 дней в регионы. Отслеживание по трек-номеру.',
  },
  {
    q: 'Подойдёт на редкие или седые брови?',
    a: 'Да. Прибор не красит, а укладывает. На редких бровях даёт визуальный объём за счёт правильного направления волосков.',
  },
  {
    q: 'Можно использовать для ресниц?',
    a: 'Да. В комплекте силиконовая насадка-кёрлер. Заменяет механический «зажим» для ресниц и безопаснее его.',
  },
  {
    q: 'Есть гарантия?',
    a: '12 месяцев от продавца AliExpress + защита покупателя (возврат при браке, помогают с возвратом).',
  },
]

const REVIEWS: { name: string; text: string; rating: number }[] = [
  {
    name: 'Анна, 27, Москва',
    text: 'Беру вместо лам. бровей в салоне — экономлю 3 500 ₽ раз в 1,5 месяца. Эффект не такой стойкий, но для ежедневного макияжа хватает с запасом.',
    rating: 5,
  },
  {
    name: 'Ольга, 34, СПб',
    text: 'Брала мужу в подарок и себе. Он в шоке, что это вообще существует. Утром 30 секунд — и брови лежат весь день.',
    rating: 5,
  },
  {
    name: 'Карина, 22, Казань',
    text: 'Ресницы тоже крутит, отдельный кёрлер выкинула. USB-C — огонь, не надо искать батарейки.',
    rating: 4,
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
            <span className="text-xl">✨</span>
            <span className="font-display text-lg font-bold tracking-tight">
              BrowLift
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium">
            <a href="#product" className="hover:text-clay">
              Продукт
            </a>
            <a href="#compare" className="hover:text-clay">
              Против салона
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
            Салон за <span className="line-through text-cocoa/40">3 500 ₽</span>.
            <br />
            Или дома за <span className="text-clay">90 секунд</span>.
          </h1>
          <p className="mt-6 text-lg md:text-xl text-cocoa/80 max-w-xl">
            BrowLift — мини-утюжок для бровей с подогревом. Прогревает волоски
            до 45 °C, ставит их в нужное направление и фиксирует на весь день.
            Эффект как после ламинирования, только без химии и записи в салон.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <div>
              <div className="text-xs uppercase tracking-wider text-cocoa/60">
                Цена с доставкой
              </div>
              <div className="flex items-baseline gap-3">
                <span className="font-display text-3xl md:text-4xl font-bold">
                  1 490 ₽
                </span>
                <span className="text-cocoa/50 line-through text-lg">
                  2 490 ₽
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

          <div className="mt-5 flex flex-wrap items-center gap-4 text-sm text-cocoa/70">
            <span className="flex items-center gap-1">
              <span>⭐️⭐️⭐️⭐️⭐️</span>
              <span className="font-medium">4.9/5</span>
            </span>
            <span>·</span>
            <span>28 000+ заказов</span>
            <span>·</span>
            <span>Доставка 10–20 дней</span>
          </div>
        </div>

        <div className="relative">
          <div className="absolute -inset-6 bg-rose/30 rounded-[40px] blur-2xl" />
          <div className="relative rounded-[32px] overflow-hidden shadow-soft border-4 border-white bg-gradient-to-br from-rose via-sand to-clay/60 h-[420px] md:h-[520px] flex items-center justify-center">
            <HeroWand />
          </div>
          <div className="absolute -bottom-5 -left-5 bg-white rounded-2xl shadow-soft px-4 py-3 flex items-center gap-3">
            <span className="text-2xl">🌡</span>
            <div>
              <div className="text-xs text-cocoa/60">Температура</div>
              <div className="font-semibold">45 °C · безопасно</div>
            </div>
          </div>
          <div className="absolute -top-4 -right-4 bg-cocoa text-cream rounded-full px-4 py-2 text-xs font-bold rotate-6 shadow-soft">
            −40% сегодня
          </div>
        </div>
      </section>

      {/* SOCIAL PROOF BAR */}
      <section className="bg-sand/60 border-y border-sand">
        <div className="mx-auto max-w-6xl px-5 py-6 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          <Stat value="90 сек" label="на обе брови" />
          <Stat value="24 ч" label="держится укладка" />
          <Stat value="45 °C" label="безопасный нагрев" />
          <Stat value="2 в 1" label="брови + ресницы" />
        </div>
      </section>

      {/* HOW IT WORKS (3 STEPS VISUAL) */}
      <section id="product" className="mx-auto max-w-6xl px-5 py-16 md:py-24">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-display text-3xl md:text-5xl font-bold">
            3 шага — и брови как на обложке
          </h2>
          <p className="mt-4 text-cocoa/80 text-lg">
            Ни тиогликолята, ни краски. Только тепло — как с утюжком для волос,
            только под брови.
          </p>
        </div>
        <div className="mt-12 grid md:grid-cols-3 gap-6">
          <HowStep
            n={1}
            emoji="🔛"
            title="Включаешь"
            text="Одна кнопка. Прогрев до 45 °C за 15 секунд. Индикатор зелёный — можно работать."
          />
          <HowStep
            n={2}
            emoji="🪮"
            title="Расчёсываешь"
            text="Ведёшь расчёской-щёточкой по брови снизу вверх. Волоски встают в нужном направлении."
          />
          <HowStep
            n={3}
            emoji="✨"
            title="Фиксируешь"
            text="Проводишь по готовой форме 5 секунд. Всё — форма держится до 24 часов."
          />
        </div>
      </section>

      {/* COLOR SELECTOR */}
      <section className="bg-white/60 border-y border-sand">
        <div className="mx-auto max-w-6xl px-5 py-16 md:py-24">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="font-display text-3xl md:text-5xl font-bold">
                Три цвета корпуса
              </h2>
              <p className="mt-4 text-cocoa/80 text-lg">
                Минималистичный soft-touch корпус, который не стыдно достать
                перед подругами в кафе.
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
                      className="flex flex-col items-center gap-2 group"
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
                          activeColor === c.id
                            ? 'text-cocoa'
                            : 'text-cocoa/60'
                        }`}
                      >
                        {c.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <ul className="mt-8 space-y-3 text-cocoa/80">
                <Check>Расчёска-щёточка для бровей в комплекте</Check>
                <Check>Силиконовая насадка для ресниц в комплекте</Check>
                <Check>Кабель USB-C + чехол-косметичка</Check>
                <Check>Инструкция на русском</Check>
              </ul>

              <a
                href={ALIEXPRESS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-10 inline-flex items-center gap-2 rounded-full bg-cocoa text-cream px-7 py-4 text-base font-semibold shadow-soft hover:bg-charcoal transition"
              >
                Заказать в цвете «
                {COLORS.find((c) => c.id === activeColor)?.label}» →
              </a>
            </div>

            <div className="grid grid-cols-3 gap-4">
              {COLORS.map((c) => (
                <div
                  key={c.id}
                  className="aspect-[3/4] rounded-3xl shadow-soft flex items-end justify-center pb-4 transition"
                  style={{ background: c.swatch }}
                >
                  <div className="bg-white/80 backdrop-blur rounded-full px-3 py-1 text-xs font-semibold text-cocoa">
                    {c.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section>
        <div className="mx-auto max-w-6xl px-5 py-16 md:py-24">
          <div className="text-center max-w-2xl mx-auto">
            <h2 className="font-display text-3xl md:text-5xl font-bold">
              Что внутри этой волшебной палочки
            </h2>
            <p className="mt-4 text-cocoa/80 text-lg">
              Керамический нагреватель, литиевый аккумулятор, термостат.
              Ничего лишнего — и ничего, чтобы сломаться.
            </p>
          </div>

          <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="bg-white rounded-3xl p-6 border border-sand hover:border-clay transition"
              >
                <div className="text-3xl">{f.emoji}</div>
                <h3 className="mt-4 font-display font-bold text-xl">
                  {f.title}
                </h3>
                <p className="mt-2 text-cocoa/70 leading-relaxed">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* COMPARE */}
      <section id="compare" className="bg-cocoa text-cream">
        <div className="mx-auto max-w-5xl px-5 py-16 md:py-24">
          <h2 className="font-display text-3xl md:text-5xl font-bold text-center">
            Салон против BrowLift
          </h2>
          <div className="mt-10 rounded-3xl overflow-hidden border border-cream/20">
            <div className="grid grid-cols-3 bg-charcoal text-cream text-sm font-semibold uppercase tracking-wider">
              <div className="p-4 border-r border-cream/10">Критерий</div>
              <div className="p-4 border-r border-cream/10">Салон</div>
              <div className="p-4 bg-clay text-cream">BrowLift</div>
            </div>
            {COMPARE.map((row, i) => (
              <div
                key={row.label}
                className={`grid grid-cols-3 text-sm md:text-base ${
                  i % 2 === 0 ? 'bg-charcoal/60' : 'bg-charcoal/40'
                }`}
              >
                <div className="p-4 border-r border-cream/10 font-semibold">
                  {row.label}
                </div>
                <div className="p-4 border-r border-cream/10 text-cream/60">
                  {row.salon}
                </div>
                <div className="p-4 font-semibold">{row.device}</div>
              </div>
            ))}
          </div>
          <div className="mt-10 text-center">
            <a
              href={ALIEXPRESS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full bg-cream text-cocoa px-8 py-4 text-lg font-bold hover:bg-rose transition"
            >
              Забрать за 1 490 ₽ →
            </a>
          </div>
        </div>
      </section>

      {/* REVIEWS */}
      <section className="mx-auto max-w-6xl px-5 py-16 md:py-24">
        <h2 className="font-display text-3xl md:text-5xl font-bold text-center">
          Что говорят
        </h2>
        <div className="mt-10 grid md:grid-cols-3 gap-6">
          {REVIEWS.map((r) => (
            <div
              key={r.name}
              className="bg-white rounded-3xl p-6 border border-sand"
            >
              <div className="text-lg">
                {'⭐️'.repeat(r.rating)}
                <span className="opacity-30">
                  {'⭐️'.repeat(5 - r.rating)}
                </span>
              </div>
              <p className="mt-4 text-cocoa/80 leading-relaxed">“{r.text}”</p>
              <div className="mt-4 text-sm font-semibold text-cocoa/60">
                — {r.name}
              </div>
            </div>
          ))}
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
              Брови как на обложке.
              <br />
              Каждое утро. За 90 секунд.
            </h2>
            <p className="mt-5 text-cream/80 text-lg max-w-xl mx-auto">
              Сегодня −40 % по промо. Завтра — обычная цена 2 490 ₽.
            </p>
            <a
              href={ALIEXPRESS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-flex items-center gap-2 rounded-full bg-cream text-cocoa px-8 py-4 text-lg font-bold hover:bg-rose transition"
            >
              Забрать за 1 490 ₽ →
            </a>
            <div className="mt-4 text-sm text-cream/60">
              Или{' '}
              <a
                href={ALIEXPRESS_BACKUP}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                запасная ссылка
              </a>
              {' · '}
              <a
                href={WHOLESALE_1688_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                опт от 50 шт (1688)
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-sand">
        <div className="mx-auto max-w-6xl px-5 py-8 flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-cocoa/60">
          <div className="flex items-center gap-2">
            <span>✨</span>
            <span className="font-display font-bold text-cocoa">BrowLift</span>
            <span>· {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-6">
            <a
              href={ALIEXPRESS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-cocoa"
            >
              AliExpress
            </a>
            <a
              href={WHOLESALE_1688_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-cocoa"
            >
              Опт (1688)
            </a>
            <a
              href={TELEGRAM_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-cocoa"
            >
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

function HowStep({
  n,
  emoji,
  title,
  text,
}: {
  n: number
  emoji: string
  title: string
  text: string
}) {
  return (
    <div className="bg-white border border-sand rounded-3xl p-6 relative">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-cocoa text-cream flex items-center justify-center font-display text-sm font-bold">
          {n}
        </div>
        <span className="text-3xl">{emoji}</span>
      </div>
      <h3 className="mt-5 font-display font-bold text-xl">{title}</h3>
      <p className="mt-2 text-cocoa/70 leading-relaxed">{text}</p>
    </div>
  )
}

function HeroWand() {
  return (
    <svg
      viewBox="0 0 400 520"
      className="w-[80%] h-[85%] drop-shadow-xl"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="BrowLift — утюжок для бровей"
    >
      <defs>
        <linearGradient id="wandBody" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#E9B8A8" />
          <stop offset="50%" stopColor="#F4D5C9" />
          <stop offset="100%" stopColor="#D9967F" />
        </linearGradient>
        <linearGradient id="wandTip" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F7F1E8" />
          <stop offset="100%" stopColor="#D9B99B" />
        </linearGradient>
        <radialGradient id="heatGlow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#FF8A65" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#FF8A65" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* soft ambient glow */}
      <circle cx="200" cy="260" r="200" fill="url(#heatGlow)" />

      {/* wand body (diagonal) */}
      <g transform="translate(200,260) rotate(-20) translate(-200,-260)">
        {/* main barrel */}
        <rect
          x="140"
          y="180"
          width="120"
          height="280"
          rx="40"
          fill="url(#wandBody)"
          stroke="#6B4435"
          strokeWidth="3"
        />

        {/* top ring */}
        <rect
          x="140"
          y="180"
          width="120"
          height="22"
          rx="11"
          fill="#6B4435"
          opacity="0.2"
        />

        {/* heating tip / comb */}
        <path
          d="M155 100 Q160 60 200 55 Q240 60 245 100 L245 180 L155 180 Z"
          fill="url(#wandTip)"
          stroke="#6B4435"
          strokeWidth="3"
        />

        {/* comb teeth */}
        <g stroke="#6B4435" strokeWidth="3" strokeLinecap="round">
          <line x1="170" y1="55" x2="170" y2="42" />
          <line x1="185" y1="51" x2="185" y2="38" />
          <line x1="200" y1="50" x2="200" y2="36" />
          <line x1="215" y1="51" x2="215" y2="38" />
          <line x1="230" y1="55" x2="230" y2="42" />
        </g>

        {/* heat shimmer above tip */}
        <g stroke="#FF8A65" strokeWidth="3" strokeLinecap="round" fill="none" opacity="0.9">
          <path d="M175 30 q5 -10 0 -20" />
          <path d="M200 25 q5 -10 0 -20" />
          <path d="M225 30 q5 -10 0 -20" />
        </g>

        {/* power button */}
        <circle
          cx="200"
          cy="260"
          r="18"
          fill="#4B2E1F"
          stroke="#F7F1E8"
          strokeWidth="3"
        />
        <circle cx="200" cy="260" r="6" fill="#FF6B4A">
          <animate
            attributeName="opacity"
            values="0.5;1;0.5"
            dur="2s"
            repeatCount="indefinite"
          />
        </circle>

        {/* LED temp indicator */}
        <rect
          x="180"
          y="320"
          width="40"
          height="6"
          rx="3"
          fill="#4B2E1F"
          opacity="0.3"
        />
        <rect x="182" y="321" width="30" height="4" rx="2" fill="#7DC27A">
          <animate
            attributeName="width"
            values="10;30;30"
            dur="1.5s"
            repeatCount="indefinite"
          />
        </rect>

        {/* USB-C port at bottom */}
        <rect
          x="182"
          y="445"
          width="36"
          height="8"
          rx="4"
          fill="#4B2E1F"
          opacity="0.6"
        />

        {/* subtle sheen */}
        <rect
          x="150"
          y="190"
          width="18"
          height="250"
          rx="9"
          fill="#F7F1E8"
          opacity="0.25"
        />
      </g>

      {/* sparkles */}
      <g fill="#F7F1E8" opacity="0.9">
        <path d="M80 120 l4 8 l8 4 l-8 4 l-4 8 l-4 -8 l-8 -4 l8 -4 z" />
        <path d="M340 90 l3 6 l6 3 l-6 3 l-3 6 l-3 -6 l-6 -3 l6 -3 z" />
        <path d="M310 450 l3 6 l6 3 l-6 3 l-3 6 l-3 -6 l-6 -3 l6 -3 z" />
        <path d="M70 420 l3 6 l6 3 l-6 3 l-3 6 l-3 -6 l-6 -3 l6 -3 z" />
      </g>
    </svg>
  )
}

export default App
