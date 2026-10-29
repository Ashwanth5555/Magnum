import { useEffect, useMemo, useState } from 'react'
import { Search, Plus, Info, Flame, Package, TriangleAlert, Sparkles } from 'lucide-react'
import { post, track } from '../lib/api'
import { Ctx, ContextSel, Ranked, CartLine } from '../lib/types'
import { usd } from '../lib/format'
import { Badge, Card, ContribBar, ErrorNote, Spinner } from '../components/ui'
import ProductImage from '../components/ProductImage'
import LiveRecoRail from '../components/LiveRecoRail'
import WhatIfStrip from '../components/WhatIfStrip'

const CATEGORIES = [
  { id: '', label: 'All' },
  { id: 'magnum', label: 'Magnum' },
  { id: 'meal', label: 'Meals' },
  { id: 'dessert', label: 'Desserts' },
  { id: 'drink', label: 'Drinks' },
  { id: 'side', label: 'Sides' },
  { id: 'grocery', label: 'Grocery' },
]


export default function Shop({
  sel, setSel, ctx, customerId, profile, cart, addToCart, onOpenCart,
}: {
  sel: ContextSel; setSel: (s: ContextSel) => void; ctx: Ctx | null
  customerId: string | null; profile: any
  cart: CartLine[]; addToCart: (sku: string, q?: number) => void; onOpenCart: () => void
}) {
  const [query, setQuery] = useState('ice cream')
  const [pending, setPending] = useState('ice cream')
  const [category, setCategory] = useState('')
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState<unknown>(null)
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setError(null)
    post<any>('/api/search', {
      query, category: category || null, customer_id: customerId,
      context: sel, cart, limit: 24,
    })
      .then((r) => { if (live) setData(r) })
      .catch((e) => live && setError(e))
    if (query) track([{ event_type: 'search', query, customer_id: customerId ?? undefined }])
    return () => { live = false }
  }, [query, category, customerId, JSON.stringify(sel), cart.length])

  const results: Ranked[] = data?.results ?? []
  const magnum = useMemo(() => results.filter((r) => r.category === 'magnum'), [results])
  const rest = useMemo(() => results.filter((r) => r.category !== 'magnum'), [results])

  // Any of these changing means the rail is answering a different question,
  // which is what the movement arrows are diffed against.
  const trigger = JSON.stringify([query, category, customerId, sel, cart.length])

  return (
    <div className="space-y-6">
      {/* search */}
      <form
        onSubmit={(e) => { e.preventDefault(); setQuery(pending) }}
        className="flex flex-wrap items-center gap-3"
      >
        <div className="relative min-w-[280px] flex-1">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-ink-500" />
          <input
            value={pending}
            onChange={(e) => setPending(e.target.value)}
            placeholder="Search Astoria Market"
            className="h-12 w-full rounded-full border border-ink-100 bg-ink-50 pl-12 pr-4 text-[15px] font-medium outline-none transition placeholder:text-ink-500 focus:border-brand-500 focus:bg-white"
          />
        </div>
        <button className="h-12 rounded-full bg-ink-900 px-6 text-[14px] font-bold text-white transition hover:bg-ink-700">
          Search
        </button>
      </form>

      {/* Shortcuts, not answers. A shopper who has typed nothing has told the
          system almost nothing, so the *order* of this row is the clearest
          statement it makes about what it thinks is going on - and it has to
          move when the weather, the hour, the occasion or the household does.
          The worked answer, with a size and a price on it, lives on the rail. */}
      {(data?.suggestions ?? []).length > 0 && (
        <div className="-mx-1 flex flex-wrap items-center gap-2 px-1">
          <span className="text-[11px] font-bold uppercase tracking-wide text-ink-400">
            Try
          </span>
          {(data?.suggestions ?? []).map((s: any) => (
            <button
              key={s.query}
              onClick={() => { setPending(s.query); setQuery(s.query) }}
              title={s.why_detail || s.why}
              className={`group flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12.5px] font-semibold transition ${
                query === s.query
                  ? 'border-ink-900 bg-ink-900 text-white'
                  : 'border-ink-200 bg-white text-ink-700 hover:border-ink-400'
              }`}
            >
              {s.query}
              <span
                className={`text-[10.5px] font-medium ${
                  query === s.query ? 'text-white/70' : 'text-ink-400'
                }`}
              >
                {s.why}
              </span>
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 border-b border-ink-100 pb-3">
        {CATEGORIES.map((c) => (
          <button
            key={c.id}
            onClick={() => {
              // Picking a category is a browse action, not a filter on the text
              // query - leaving "ice cream" applied would hide most of the aisle.
              setCategory(c.id)
              if (c.id) { setQuery(''); setPending('') }
            }}
            className={`rounded-full px-3.5 py-2 text-[13px] font-semibold transition ${
              category === c.id ? 'bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-500/25' : 'text-ink-500 hover:bg-ink-50'
            }`}
          >
            {c.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 text-[12px] text-ink-500">
          {data && (
            <>
              <Badge tone={data.intent?.intent_class === 'direct' ? 'brand' : 'neutral'}>
                intent: {data.intent?.intent_class}
              </Badge>
              <span>{data.results.length} results · {data.latency_ms} ms</span>
            </>
          )}
        </div>
      </div>


      {error ? <ErrorNote error={error} /> : null}
      {!data && !error && <Spinner label="Ranking" />}

      {/* The rail sits beside the results, not inside them: it has to survive
          any query and any category the shopper browses into. */}
      <div className="flex flex-col gap-6 xl:grid xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="order-2 min-w-0 space-y-6 xl:order-1">
        {/* why this order */}
        {data && (
          <Card className="bg-ink-50/60 px-4 py-3">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[12px] text-ink-700">
              <span className="font-bold text-ink-900">What is deciding this order</span>
              {/* These are the weights actually in force, not the published
                  defaults. When the shopper is looking at something a Magnum
                  pairs with, a sixth factor switches on and the other five
                  compress to make room — and the strip has to show that
                  happening, or the one moment the system is most obviously
                  reasoning is the one moment the screen goes quiet. */}
              {((data.rail_weights ?? []) as { family: string; label?: string; weight: number }[]).map((c) => (
                <span key={c.family} className="flex items-center gap-1.5">
                  <span className={`h-2.5 w-2.5 rounded-full ${
                    { text: 'bg-ink-300', personal: 'bg-brand-500', peer: 'bg-brand-200',
                      context: 'bg-warn-500', availability: 'bg-cool-500',
                      pairing: 'bg-violet-500' }[c.family] ?? 'bg-ink-300'
                  }`} />
                  {c.label ?? c.family} {(c.weight * 100).toFixed(0)}%
                </span>
              ))}
              <span className="text-ink-500">
                {data.pairing?.active
                  ? `Pairing is live — ${data.pairing.baskets?.toLocaleString()} past baskets with what you are looking at.`
                  : data.personalised
                    ? `Personalised for ${profile?.display_name ?? 'this household'} (${profile?.cluster?.short}).`
                    : 'Guest session — the personal weight moves to weather and what is in stock.'}
              </span>
            </div>
          </Card>
        )}
        {data && <WhatIfStrip sel={sel} setSel={setSel} customerId={customerId} />}
          {magnum.length > 0 && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-brand-600" />
                <h2 className="text-[17px] font-bold tracking-tight">Magnum</h2>
                {ctx && ctx.heat_pull >= 0.72 && (
                  <Badge tone="warn"><Flame className="h-3 w-3" /> {Math.round(ctx.temperature_f)}°F pulls frozen dessert up</Badge>
                )}
              </div>
              <Grid items={magnum} open={open} setOpen={setOpen} addToCart={addToCart} />
            </div>
          )}

          {rest.length > 0 && (
            <div>
              <h2 className="mb-3 text-[17px] font-bold tracking-tight">
                {magnum.length ? 'Also in this basket’s world' : 'Results'}
              </h2>
              <Grid items={rest} open={open} setOpen={setOpen} addToCart={addToCart} />
            </div>
          )}

          {data && results.length === 0 && (
            <div className="rounded-2xl border border-dashed border-ink-100 py-16 text-center text-[14px] text-ink-500">
              <div className="font-semibold text-ink-700">Nothing matched “{query}”.</div>
              <div className="mt-1">
                The Magnum rail is still live on the right — it is ranked
                independently of the search box on purpose.
              </div>
            </div>
          )}
        </div>

        {data && (
          <LiveRecoRail
            items={data.magnum_live ?? []}
            signals={data.signals ?? []}
            latency={data.latency_ms}
            personalised={data.personalised}
            who={profile?.display_name ?? 'this household'}
            onAdd={addToCart}
            trigger={trigger}
            pairing={data.pairing ?? null}
          />
        )}
      </div>

      {cart.length > 0 && (
        <button
          onClick={onOpenCart}
          className="fixed bottom-6 right-6 z-30 flex items-center gap-3 rounded-full bg-brand-500 px-5 py-3.5 text-[14px] font-bold text-white shadow-lg shadow-brand-500/25 transition hover:bg-brand-600"
        >
          Go to cart · {cart.reduce((a, l) => a + l.quantity, 0)} items
        </button>
      )}
    </div>
  )
}

function Grid({
  items, open, setOpen, addToCart,
}: { items: Ranked[]; open: string | null; setOpen: (s: string | null) => void; addToCart: (s: string, q?: number) => void }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {items.map((p, i) => (
        <ProductCard key={p.sku_id} p={p} rank={i + 1} open={open === p.sku_id}
                     onToggle={() => setOpen(open === p.sku_id ? null : p.sku_id)} addToCart={addToCart} />
      ))}
    </div>
  )
}

function ProductCard({
  p, rank, open, onToggle, addToCart,
}: { p: Ranked; rank: number; open: boolean; onToggle: () => void; addToCart: (s: string, q?: number) => void }) {
  const out = p.stock_state === 'out_of_stock'
  const low = p.stock_state === 'low_stock'
  return (
    <Card className="group flex flex-col overflow-hidden transition hover:border-ink-300">
      <div className="relative h-32">
        <ProductImage sku={p.sku_id} name={p.name} category={p.category} flavour={p.flavour} rounded="" className="h-32 w-full" />
        <div className="absolute left-2 top-2 flex gap-1">
          {p.units_in_pack > 1 && (
            <span className="rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-bold text-ink-900">
              {p.units_in_pack}-count
            </span>
          )}
          {out && <span className="rounded-full bg-risk-500 px-2 py-0.5 text-[10px] font-bold text-white">Sold out</span>}
          {!out && low && <span className="rounded-full bg-warn-50 px-2 py-0.5 text-[10px] font-bold text-warn-500">Only {p.on_hand} left</span>}
        </div>
        <span className="absolute right-2 top-2 rounded-full bg-black/45 px-1.5 py-0.5 text-[10px] font-bold text-white tabular-nums">
          #{rank}
        </span>
        <button
          onClick={() => !out && addToCart(p.sku_id)}
          disabled={out}
          className="absolute bottom-2 right-2 z-10 grid h-8 w-8 place-items-center rounded-full bg-white text-ink-900 shadow transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-40"
          title={out ? 'Out of stock' : 'Add to cart'}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-1 p-3">
        <div className="line-clamp-2 text-[13px] font-bold leading-tight text-ink-900">{p.name}</div>
        <div className="text-[12px] text-ink-500">{p.size_label}</div>
        <div className="mt-auto flex items-center justify-between pt-2">
          <span className="text-[14px] font-bold tabular-nums">{usd(p.price)}</span>
          <button
            onClick={onToggle}
            className={`flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold transition ${
              open ? 'bg-ink-900 text-white' : 'text-ink-500 hover:bg-ink-50'
            }`}
          >
            <Info className="h-3 w-3" /> Why
          </button>
        </div>
        <ContribBar items={p.contributions} />

        {open && (
          <div className="rise mt-2 space-y-2 rounded-xl bg-ink-50 p-3">
            <div className="flex items-baseline justify-between text-[11px] font-bold text-ink-900">
              <span>Match score</span>
              <span className="tabular-nums">{p.match_score.toFixed(4)}</span>
            </div>
            <table className="w-full text-[11px] text-ink-700">
              <tbody>
                {p.contributions.map((c) => (
                  <tr key={c.family}>
                    <td className="py-0.5">{c.label ?? c.family}</td>
                    <td className="py-0.5 text-right tabular-nums text-ink-500">
                      {c.score.toFixed(2)} × {c.weight}
                    </td>
                    <td className="py-0.5 text-right font-semibold tabular-nums">{c.points.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {p.reasons.length > 0 && (
              <ul className="space-y-1 border-t border-ink-100 pt-2 text-[11px] leading-snug text-ink-700">
                {p.reasons.map((r) => (
                  <li key={r.code} className="flex gap-1.5">
                    <span className="mt-[3px] h-1 w-1 shrink-0 rounded-full bg-brand-500" />
                    {r.customer}
                  </li>
                ))}
              </ul>
            )}
            {out && (
              <div className="flex items-start gap-1.5 border-t border-ink-100 pt-2 text-[11px] text-risk-500">
                <TriangleAlert className="mt-[1px] h-3 w-3 shrink-0" />
                Out of stock: the score is damped so it can never outrank an available substitute.
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
