import { useCallback, useEffect, useMemo, useState } from 'react'
import { Store, ShoppingBag, LineChart, Database, IceCream2, UserRound, TrendingUp } from 'lucide-react'
import { get, post, track } from './lib/api'
import { Ctx, ContextSel, CartLine } from './lib/types'
import ScenarioBar from './components/ScenarioBar'
import Impact from './screens/Impact'
import Shop from './screens/Shop'
import Cart from './screens/Cart'
import DemandDesk from './screens/DemandDesk'
import DataExplorer from './screens/DataExplorer'
import Customer from './screens/Customer'
import ChangeFeed, { useChangeFeed } from './components/ChangeFeed'
import { ScreenBoundary, Spinner } from './components/ui'

const NAV = [
  { id: 'impact', label: 'Impact', icon: TrendingUp, hint: 'What a month, a quarter and half a year of this add up to' },
  { id: 'shop', label: 'Shop', icon: Store, hint: 'Context-aware search' },
  { id: 'cart', label: 'Cart', icon: ShoppingBag, hint: 'Quantity and offer' },
  { id: 'customer', label: 'Customer', icon: UserRound, hint: 'Everything the log knows about this household' },
  { id: 'desk', label: 'Demand desk', icon: LineChart, hint: 'Forecast and stock' },
  { id: 'data', label: 'Data', icon: Database, hint: 'Explore the tables' },
] as const
type Tab = (typeof NAV)[number]['id']

const DEFAULT_SEL: ContextSel = {
  day: 'friday', time_window: 'evening', season: 'summer', weather: 'hot',
  game_day: true, event: 'none', activity: 'high', area_id: 'astoria',
}

export default function App() {
  const [tab, setTab] = useState<Tab>('shop')
  const [sel, setSel] = useState<ContextSel>(DEFAULT_SEL)
  const [ctx, setCtx] = useState<Ctx | null>(null)
  const [options, setOptions] = useState<any>(null)
  const [meta, setMeta] = useState<any>(null)
  const [profiles, setProfiles] = useState<any[]>([])
  const [customerId, setCustomerId] = useState<string | null>('CUS-000001')
  const [cart, setCart] = useState<CartLine[]>([])

  useEffect(() => {
    Promise.all([
      get<any>('/api/context/options'),
      get<any>('/api/meta'),
      get<any>('/api/demo/profiles'),
    ]).then(([o, m, p]) => { setOptions(o); setMeta(m); setProfiles(p.profiles) })
  }, [])

  useEffect(() => {
    post<any>('/api/context/resolve', sel).then((r) => setCtx(r.context))
  }, [sel])

  useEffect(() => {
    if (ctx) track([{ event_type: 'context_changed', context_id: ctx.context_id, customer_id: customerId ?? undefined }])
  }, [ctx?.context_id])

  const feed = useChangeFeed(ctx)

  const profile = useMemo(
    () => profiles.find((p) => p.customer_id === customerId) ?? null,
    [profiles, customerId],
  )

  const addToCart = useCallback((sku_id: string, quantity = 1) => {
    setCart((c) => {
      const i = c.findIndex((l) => l.sku_id === sku_id)
      if (i < 0) return [...c, { sku_id, quantity }]
      const next = [...c]
      next[i] = { ...next[i], quantity: next[i].quantity + quantity }
      return next
    })
    track([{ event_type: 'add_to_cart', sku_id, customer_id: customerId ?? undefined, context_id: ctx?.context_id }])
  }, [customerId, ctx?.context_id])

  const setQty = useCallback((sku_id: string, quantity: number) => {
    setCart((c) => quantity <= 0 ? c.filter((l) => l.sku_id !== sku_id)
      : c.map((l) => (l.sku_id === sku_id ? { ...l, quantity } : l)))
  }, [])

  const resetDemo = useCallback(() => {
    post('/api/demo/reset', {}).then(() => { setCart([]); setSel(DEFAULT_SEL); setCustomerId('CUS-000001') })
  }, [])

  const cartUnits = cart.reduce((a, l) => a + l.quantity, 0)

  if (!options || !meta) {
    return <div className="grid h-full place-items-center"><Spinner label="Starting the console" /></div>
  }

  return (
    <div className="min-h-full bg-white">
      <header className="border-b border-ink-100">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
          <div className="flex shrink-0 items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand-500 text-white">
              <IceCream2 className="h-[18px] w-[18px]" />
            </span>
            <div className="leading-tight">
              <div className="text-[15px] font-bold tracking-tight whitespace-nowrap">Magnum Now</div>
              <div className="whitespace-nowrap text-[10px] font-semibold uppercase tracking-wider text-ink-500">
                {meta.market}
              </div>
            </div>
          </div>

          <nav className="order-3 flex w-full items-center gap-1 overflow-x-auto no-scrollbar lg:order-none lg:ml-2 lg:w-auto">
            {NAV.map((n) => {
              const Icon = n.icon
              const on = tab === n.id
              return (
                <button
                  key={n.id}
                  onClick={() => { setTab(n.id); track([{ event_type: 'screen_view', banner_id: n.id }]) }}
                  title={n.hint}
                  className={`flex shrink-0 items-center gap-2 rounded-full px-3.5 py-2 text-[13px] font-semibold transition ${
                    on ? 'bg-ink-900 text-white' : 'text-ink-700 hover:bg-ink-50'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {n.label}
                  {n.id === 'cart' && cartUnits > 0 && (
                    <span className={`rounded-full px-1.5 text-[11px] ${on ? 'bg-white/20' : 'bg-brand-500 text-white'}`}>
                      {cartUnits}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>

          <div className="ml-auto flex shrink-0 items-center gap-2">
            {customerId && (
              <button
                onClick={() => setTab('customer')}
                title="Open this household's analytics"
                className={`hidden rounded-full px-3 py-2 text-[12px] font-bold transition sm:block ${
                  tab === 'customer' ? 'bg-brand-500 text-white' : 'bg-brand-50 text-brand-700 hover:bg-brand-100'
                }`}
              >
                View analytics
              </button>
            )}
          </div>
        </div>
      </header>

      <ScenarioBar sel={sel} setSel={setSel} ctx={ctx} options={options} onReset={resetDemo}
                   profiles={profiles} customerId={customerId} setCustomerId={setCustomerId} />

      {feed.length > 0 && (
        <div className="mx-auto max-w-[1500px] px-5 pt-3">
          <ChangeFeed feed={feed} />
        </div>
      )}

      <main className="mx-auto max-w-[1500px] px-5 py-6">
       <ScreenBoundary key={tab} name={NAV.find((n) => n.id === tab)?.label ?? tab}>
        {tab === 'impact' && <Impact />}
        {tab === 'shop' && (
          <Shop sel={sel} setSel={setSel} ctx={ctx} customerId={customerId} profile={profile}
                cart={cart} addToCart={addToCart} onOpenCart={() => setTab('cart')} />
        )}
        {tab === 'customer' && (
          <Customer customerId={customerId} onShop={() => setTab('shop')} sel={sel} />
        )}
        {tab === 'cart' && (
          <Cart sel={sel} ctx={ctx} customerId={customerId} profile={profile}
                cart={cart} setQty={setQty} addToCart={addToCart} onShop={() => setTab('shop')} />
        )}
        {tab === 'desk' && <DemandDesk sel={sel} ctx={ctx} />}
        {tab === 'data' && <DataExplorer meta={meta} />}
       </ScreenBoundary>
      </main>

      <footer className="border-t border-ink-100 bg-ink-50/50">
        <div className="mx-auto max-w-[1500px] px-5 py-5 text-[12px] leading-relaxed text-ink-500">
          <strong className="text-ink-700">{meta.disclaimer}</strong>
          <br />
          Policy {meta.policy_version} · forecast {meta.forecast_version} · generator {meta.generator_version} ·
          seed {meta.seed} · window {meta.window.start.slice(0, 10)} → {meta.window.end.slice(0, 10)} ({meta.window.weeks} weeks).
          Held out of the application: {meta.held_out_tables.join(', ')}.
        </div>
      </footer>
    </div>
  )
}
