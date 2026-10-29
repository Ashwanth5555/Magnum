import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Link2, Minus, Plus, Trash2, Tag, TicketX, Users } from 'lucide-react'
import { post } from '../lib/api'
import { Ctx, ContextSel, CartLine, Decision } from '../lib/types'
import { usd, pct } from '../lib/format'
import { Badge, Card, ErrorNote, Section } from '../components/ui'
import ProductImage from '../components/ProductImage'

export default function Cart({
  sel, ctx, customerId, profile, cart, setQty, addToCart, onShop,
}: {
  sel: ContextSel; ctx: Ctx | null; customerId: string | null; profile: any
  cart: CartLine[]; setQty: (s: string, q: number) => void
  addToCart: (s: string, q?: number) => void; onShop: () => void
}) {
  const [catalog, setCatalog] = useState<any>(null)
  const [rec, setRec] = useState<any>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => { fetch('/api/catalog').then((r) => r.json()).then(setCatalog) }, [])

  useEffect(() => {
    if (!cart.length) { setRec(null); setDecision(null); return }
    setError(null)
    post<any>('/api/cart/recommend', { customer_id: customerId, context: sel, cart })
      .then(setRec).catch(setError)
  }, [JSON.stringify(cart), customerId, JSON.stringify(sel)])

  useEffect(() => {
    post<Decision>('/api/offers/decide', {
      customer_id: customerId, context: sel, cart,
      recommended_sku: rec?.sku_id ?? null,
    }).then(setDecision).catch(setError)
  }, [rec?.sku_id, JSON.stringify(cart), customerId, JSON.stringify(sel)])

  const byId: Record<string, any> = {}
  ;(catalog?.products ?? []).forEach((p: any) => (byId[p.sku_id] = p))
  const subtotal = cart.reduce((a, l) => a + (byId[l.sku_id]?.price ?? 0) * l.quantity, 0)

  if (!cart.length) {
    return (
      <div className="rounded-2xl border border-dashed border-ink-100 py-20 text-center">
        <p className="text-[15px] font-semibold text-ink-900">Your cart is empty</p>
        <p className="mt-1 text-[13px] text-ink-500">
          Add a meal and watch the occasion model size the dessert.
        </p>
        <button onClick={onShop} className="mt-5 rounded-full bg-ink-900 px-5 py-2.5 text-[13px] font-bold text-white">
          Browse the store
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="space-y-6">
        <Section title="Your cart" subtitle={`${cart.length} lines · ${cart.reduce((a, l) => a + l.quantity, 0)} items`}>
          <Card className="divide-y divide-ink-100">
            {cart.map((l) => {
              const p = byId[l.sku_id]
              if (!p) return null
              return (
                <div key={l.sku_id} className="flex items-center gap-3 p-3">
                  <ProductImage sku={p.sku_id} name={p.name} category={p.category} flavour={p.flavour} className="h-14 w-14 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-bold">{p.name}</div>
                    <div className="text-[12px] text-ink-500">{p.size_label} · {usd(p.price)}</div>
                  </div>
                  <div className="flex items-center gap-1 rounded-full border border-ink-100 p-0.5">
                    <button onClick={() => setQty(l.sku_id, l.quantity - 1)} className="grid h-7 w-7 place-items-center rounded-full hover:bg-ink-50">
                      {l.quantity === 1 ? <Trash2 className="h-3.5 w-3.5 text-risk-500" /> : <Minus className="h-3.5 w-3.5" />}
                    </button>
                    <span className="w-6 text-center text-[13px] font-bold tabular-nums">{l.quantity}</span>
                    <button onClick={() => setQty(l.sku_id, l.quantity + 1)} className="grid h-7 w-7 place-items-center rounded-full hover:bg-ink-50">
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="w-16 text-right text-[13px] font-bold tabular-nums">
                    {usd(p.price * l.quantity)}
                  </div>
                </div>
              )
            })}
            <div className="flex items-center justify-between p-3 text-[14px] font-bold">
              <span>Subtotal</span>
              <span className="tabular-nums">{usd(subtotal)}</span>
            </div>
          </Card>
        </Section>

        {error && <ErrorNote error={error} />}

        {rec && <QuantityPanel rec={rec} addToCart={addToCart} profile={profile} decision={decision} />}
        {rec?.pairing && <BasketPairing rec={rec} />}
        {rec && <BasketChanges rec={rec} cart={cart} />}
      </div>
    </div>
  )
}

function QuantityPanel({ rec, addToCart, profile, decision }: {
  rec: any; addToCart: (s: string, q?: number) => void; profile: any; decision: Decision | null
}) {
  const inputs = rec.inputs
  const occ = rec.occasion
  const rows = [
    { k: 'personal', label: profile ? `${profile.display_name}'s usual` : 'Personal history', v: inputs.personal_avg_units, w: inputs.weights.personal },
    { k: 'peer', label: 'Similar households', v: inputs.peer_avg_units, w: inputs.weights.peer },
    { k: 'occasion', label: 'This occasion', v: inputs.occasion_units, w: inputs.weights.occasion },
  ]
  return (
    <Section
      title="How many, and why"
      subtitle="How many bars: 40% what this household normally buys, 35% what similar households buy, 25% the size of tonight’s occasion — then rounded to a pack that actually exists on the shelf."
    >
      <Card className="overflow-hidden">
        <div className="flex items-center gap-4 border-b border-ink-100 p-4">
          <ProductImage sku={rec.sku_id} name={rec.name} category={rec.category} flavour={rec.flavour} className="h-16 w-16 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-[14px] font-bold">{rec.name}</div>
            <div className="text-[12px] text-ink-500">
              {usd(rec.price)} · {rec.units_in_pack > 1 ? `${rec.units_in_pack}-count` : 'single'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Recommend</div>
            <div className="text-3xl font-bold tabular-nums text-brand-600">{rec.quantity}</div>
            <div className="text-[11px] text-ink-500">{rec.units_delivered} bars</div>
          </div>
          <button
            onClick={() => addToCart(rec.sku_id, rec.quantity)}
            className="rounded-full bg-brand-500 px-4 py-2.5 text-[13px] font-bold text-white transition hover:bg-brand-600"
          >
            Add {rec.quantity}
          </button>
        </div>

        {decision && <OfferBanner d={decision} />}

        <table className="w-full text-[12px]">
          <thead className="bg-ink-50 text-[10px] font-bold uppercase tracking-wider text-ink-500">
            <tr>
              <th className="px-4 py-2 text-left">Input</th>
              <th className="px-4 py-2 text-right">Units</th>
              <th className="px-4 py-2 text-right">Weight</th>
              <th className="px-4 py-2 text-right">Contribution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {rows.map((r) => (
              <tr key={r.k}>
                <td className="px-4 py-2 font-semibold text-ink-900">{r.label}</td>
                <td className="px-4 py-2 text-right tabular-nums">{r.v.toFixed(2)}</td>
                <td className="px-4 py-2 text-right tabular-nums text-ink-500">{r.w}</td>
                <td className="px-4 py-2 text-right font-semibold tabular-nums">{(r.v * r.w).toFixed(2)}</td>
              </tr>
            ))}
            <tr className="bg-ink-50/40">
              <td className="px-4 py-2 font-semibold text-ink-700">Basket subtotal</td>
              <td colSpan={2} />
              <td className="px-4 py-2 text-right font-semibold tabular-nums">
                {(rec.q_before_context ?? rec.q_raw).toFixed(3)}
              </td>
            </tr>
            {/* The hour's own pull on the size. The weather, the match and how
                many people are ordering right now all move the count, and until
                this row existed they moved it silently. */}
            {(rec.context_terms ?? []).map((t: any) => (
              <tr key={t.code}>
                <td className="px-4 py-2 font-semibold text-ink-900" title={t.detail}>
                  {t.label}
                </td>
                <td colSpan={2} className="px-4 py-2 text-right text-[11.5px] leading-snug text-ink-500">
                  {t.detail}
                </td>
                <td
                  className={`px-4 py-2 text-right font-semibold tabular-nums ${
                    t.multiplier >= 1 ? 'text-brand-700' : 'text-rose-500'
                  }`}
                >
                  ×{t.multiplier.toFixed(2)}
                </td>
              </tr>
            ))}
            <tr className="bg-ink-50/60">
              <td className="px-4 py-2 font-bold">Bars before rounding</td>
              <td colSpan={2} />
              <td className="px-4 py-2 text-right font-bold tabular-nums">{rec.q_raw.toFixed(3)}</td>
            </tr>
          </tbody>
        </table>

        <div className="space-y-2 border-t border-ink-100 p-4">
          <div className="flex items-center gap-2 text-[12px] font-bold text-ink-900">
            <Users className="h-3.5 w-3.5 text-brand-600" />
            Occasion read: {occ.occasion_size} {occ.occasion_size === 1 ? 'person' : 'people'}
            <Badge tone="neutral">confidence {pct(occ.confidence, 0)}</Badge>
          </div>
          <div className="text-[12px] leading-relaxed text-ink-500">
            {occ.evidence?.length
              ? `${occ.evidence.join('; ')}.`
              : `${occ.meal_portions} meal portions, ${occ.drinks} drinks, ${occ.shareables} shareable items in the basket.`}
            {' '}Raw estimate {occ.raw_estimate}, rounded to {occ.occasion_size}.
          </div>
          {rec.reasons?.length > 0 && (
            <ul className="space-y-1 pt-1 text-[12px] leading-snug text-ink-700">
              {rec.reasons.map((r: any) => (
                <li key={r.code} className="flex gap-2">
                  <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full bg-brand-500" />
                  {r.customer}
                </li>
              ))}
            </ul>
          )}
          {rec.alternatives?.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-ink-100 pt-3">
              <span className="text-[11px] font-bold uppercase tracking-wider text-ink-500">Packs considered</span>
              {rec.alternatives.map((a: any) => (
                <Badge key={a.sku_id} tone="neutral">
                  {a.name.replace('Magnum ', '')} · {usd(a.unit_price)}/bar · {a.on_hand} on hand
                </Badge>
              ))}
            </div>
          )}
        </div>
      </Card>
    </Section>
  )
}

/**
 * The offer, as the shopper would meet it.
 *
 * This used to be a full decision panel - every candidate arm, its expected
 * incremental margin, the guardrail grid, and chips to force each refusal
 * state. That is the right view for someone auditing the policy and the wrong
 * one for someone buying ice cream, and it dominated a screen whose job is to
 * say "how many, and why".
 *
 * So the ranking still happens server-side, unchanged; only the winner reaches
 * the glass, attached to the suggestion it applies to. When the policy declines
 * - a guardrail, or no arm that pays for itself - the banner is simply absent.
 * Nothing announces the silence to the shopper. The full reasoning now lives on
 * the customer screen, where the audience for it actually is.
 */
function OfferBanner({ d }: { d: Decision }) {
  // The coupon block is built server-side so the cart, the suggestion cards and
  // the reorder push all describe the same decision the same way. It renders in
  // both directions on purpose: the interesting half of this system is the half
  // that declines to discount, and an absence with no copy on it reads as a bug.
  const c = (d as any).coupon as
    | { has_coupon: boolean; kind: string; label: string | null; discount_pct: number
        saving: number; why: string; slot: string | null; who: string | null
        season_note: string }
    | undefined
  if (!c) return null
  const disc = c.has_coupon && c.discount_pct > 0
  return (
    <div
      className={`flex items-start gap-3 border-t px-4 py-3 ${
        disc ? 'border-brand-500/20 bg-brand-50' : 'border-ink-100 bg-ink-50/70'
      }`}
    >
      <span
        className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full text-white ${
          disc ? 'bg-brand-500' : 'bg-ink-300'
        }`}
      >
        {disc ? <Tag className="h-4 w-4" /> : <TicketX className="h-4 w-4" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className={`text-[13px] font-bold ${disc ? 'text-brand-700' : 'text-ink-700'}`}>
          {c.label}
        </div>
        {disc && c.saving > 0 && (
          <div className="text-[11.5px] leading-snug text-brand-700/80">
            Saves {usd(c.saving)} on this suggestion — applied at checkout.
          </div>
        )}
        <div
          className={`mt-1 flex items-start gap-1.5 text-[11.5px] leading-snug ${
            disc ? 'text-brand-700/80' : 'text-ink-600'
          }`}
        >
          <span
            className={`mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full ${
              disc ? 'bg-brand-600' : 'bg-ink-300'
            }`}
          />
          {c.why}
        </div>
        {c.slot && (
          <div className={`mt-1 pl-3 text-[11.5px] leading-snug ${disc ? 'text-brand-700/80' : 'text-ink-600'}`}>
            {c.slot}
          </div>
        )}
        {c.who && (
          <div className={`mt-1 pl-3 text-[11.5px] leading-snug ${disc ? 'text-brand-700/80' : 'text-ink-600'}`}>
            {c.who}
          </div>
        )}
        <div className={`mt-1 text-[11.5px] font-medium leading-snug ${disc ? 'text-brand-700/70' : 'text-ink-500'}`}>
          {c.season_note}
        </div>
      </div>
      {disc && (
        <span className="mt-0.5 shrink-0 rounded-full bg-white px-2.5 py-1 text-[11px] font-bold tabular-nums text-brand-700">
          −{Math.round(c.discount_pct * 100)}%
        </span>
      )}
    </div>
  )
}


/**
 * What the basket itself is telling the recommendation.
 *
 * The cart is the strongest signal in the product and it used to be spent on a
 * headcount. It carries more than that: what somebody is eating moves which
 * flavour goes with it and how many bars the occasion takes, and both of those
 * are measurable in the order log rather than matters of taste.
 */
function BasketPairing({ rec }: { rec: any }) {
  const p = rec.pairing
  const pull = Object.entries(p.flavour_pull as Record<string, number>)
    .sort((a, b) => b[1] - a[1])
  const switched = p.base_flavour !== p.chosen_flavour
  const bigger = p.units_ratio >= 1.08
  const smaller = p.units_ratio <= 0.92

  return (
    <Section
      title="What's in the basket changes the answer"
      subtitle="Flavour affinity and basket size, measured across real co-purchase baskets in the order log — not a merchandising rule."
    >
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-ink-100 bg-violet-50/60 px-4 py-3">
          <Link2 className="h-4 w-4 shrink-0 text-violet-700" />
          <span className="text-[12.5px] text-ink-700">
            Pairing against{' '}
            <span className="font-bold text-ink-900">
              {p.anchors.map((a: any) => a.name).join(', ')}
            </span>
          </span>
          <span className="ml-auto rounded-full bg-white px-2.5 py-1 text-[11px] font-bold tabular-nums text-violet-700">
            {p.anchors.reduce((a: number, x: any) => a + (x.n ?? 0), 0).toLocaleString()} baskets
          </span>
        </div>

        <div className="grid gap-4 p-4 sm:grid-cols-2">
          {/* flavour */}
          <div>
            <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-ink-500">
              Flavour pull
            </div>
            <div className="space-y-1.5">
              {pull.map(([f, v]) => {
                const chosen = f === p.chosen_flavour
                return (
                  <div key={f} className="flex items-center gap-2 text-[11.5px]">
                    <span className={`w-14 shrink-0 ${chosen ? 'font-bold text-ink-900' : 'text-ink-500'}`}>
                      {f}
                    </span>
                    <span className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-ink-100">
                      <span
                        className={`absolute top-0 h-full ${v >= 1 ? 'bg-violet-500' : 'bg-ink-300'}`}
                        style={{
                          left: v >= 1 ? '50%' : `${50 - Math.min(50, (1 - v) * 55)}%`,
                          width: `${Math.min(50, Math.abs(v - 1) * 55)}%`,
                        }}
                      />
                      <span className="absolute left-1/2 top-0 h-full w-px bg-ink-200" />
                    </span>
                    <span className={`w-11 shrink-0 text-right font-bold tabular-nums ${
                      v >= 1.15 ? 'text-violet-700' : v <= 0.85 ? 'text-ink-400' : 'text-ink-500'
                    }`}>
                      {v.toFixed(2)}×
                    </span>
                  </div>
                )
              })}
            </div>
            <p className="mt-2.5 text-[11.5px] leading-snug text-ink-700">
              {switched ? (
                <>
                  <span className="font-semibold text-violet-700">Moved off the usual.</span>{' '}
                  This household normally takes <span className="font-semibold">{p.base_flavour}</span>,
                  but what is in the basket pulls hard enough toward{' '}
                  <span className="font-semibold">{p.chosen_flavour}</span> to change the pick.
                </>
              ) : (
                <>
                  <span className="font-semibold text-ink-900">Usual flavour holds.</span>{' '}
                  <span className="font-semibold">{p.base_flavour}</span> is strong enough in this
                  household's history that the pairing tilts the ranking without overturning it.
                </>
              )}
            </p>
          </div>

          {/* size */}
          <div className="sm:border-l sm:border-ink-100 sm:pl-4">
            <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-ink-500">
              Size pull
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-3xl font-bold tabular-nums ${
                bigger ? 'text-violet-700' : smaller ? 'text-cool-500' : 'text-ink-900'
              }`}>
                {p.units_ratio.toFixed(2)}×
              </span>
              <span className="text-[12px] text-ink-500">the bars of an average basket</span>
            </div>
            <div className="mt-2 flex items-center gap-2 text-[12px] text-ink-700">
              <span className="tabular-nums text-ink-500">{(rec.q_raw / p.units_ratio).toFixed(2)} bars</span>
              <ArrowRight className="h-3.5 w-3.5 text-ink-300" />
              <span className="font-bold tabular-nums">{rec.q_raw.toFixed(2)}</span>
              <ArrowRight className="h-3.5 w-3.5 text-ink-300" />
              <span className="font-bold tabular-nums text-brand-600">{rec.units_delivered} bars</span>
            </div>
            <p className="mt-2.5 text-[11.5px] leading-snug text-ink-700">
              {bigger
                ? 'Shared dishes. Baskets built around these carry materially more dessert, so the pack sizes rank above the singles.'
                : smaller
                ? 'Single-serve. Baskets built around these carry less dessert than average, so a single bar outranks a pack.'
                : 'Neutral. Nothing in the basket argues for a bigger or a smaller dessert than this household usually takes.'}
            </p>
            <div className="mt-3 space-y-1 border-t border-ink-100 pt-2.5">
              {p.anchors.map((a: any) => (
                <div key={a.sku_id} className="flex items-center gap-2 text-[11px]">
                  <span className="min-w-0 flex-1 truncate text-ink-700">{a.name}</span>
                  <span className="shrink-0 text-ink-500">pulls {a.top_flavour}</span>
                  <span className="w-10 shrink-0 text-right font-bold tabular-nums text-ink-900">
                    {a.units_ratio.toFixed(2)}×
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </Section>
  )
}

/**
 * A running log of what each basket edit did.
 *
 * Watching a number change is not the same as being told why it changed. The
 * recommendation moves the moment a line is added or removed, and without this
 * the movement reads as flicker; with it, each edit gets a sentence naming the
 * cause and the effect.
 */
function BasketChanges({ rec, cart }: { rec: any; cart: CartLine[] }) {
  const [log, setLog] = useState<{ id: number; text: string; delta: string }[]>([])
  const prev = useRef<{ units: number; flavour: string; people: number; sku: string } | null>(null)
  const seq = useRef(0)

  useEffect(() => {
    const now = {
      units: rec.units_delivered as number,
      flavour: (rec.pairing?.chosen_flavour ?? rec.flavour ?? '') as string,
      people: rec.occasion.occasion_size as number,
      sku: rec.name as string,
    }
    const before = prev.current
    prev.current = now
    if (!before) return

    const parts: string[] = []
    if (now.people !== before.people) {
      parts.push(`occasion ${before.people} → ${now.people} ${now.people === 1 ? 'person' : 'people'}`)
    }
    if (now.flavour !== before.flavour) {
      parts.push(`flavour ${before.flavour} → ${now.flavour}`)
    }
    if (now.units !== before.units) {
      parts.push(`size ${before.units} → ${now.units} bars`)
    }
    if (now.sku !== before.sku) parts.push(`pack ${now.sku.replace('Magnum ', '')}`)
    if (!parts.length) return

    seq.current += 1
    setLog((l) => [{
      id: seq.current,
      text: parts.join(' · '),
      delta: now.units > before.units ? 'up' : now.units < before.units ? 'down' : 'flat',
    }, ...l].slice(0, 6))
  }, [rec.units_delivered, rec.occasion.occasion_size, rec.name, rec.pairing?.chosen_flavour])

  if (!log.length) {
    return (
      <p className="rounded-2xl border border-dashed border-ink-100 px-4 py-3 text-[12px] leading-snug text-ink-500">
        Add or remove a line and the recommendation re-derives — occasion size, flavour
        and pack all move together, and each change is logged here with its cause.
      </p>
    )
  }

  return (
    <Section title="What your last edits changed" subtitle="Every basket edit re-runs the whole derivation. This is the trace.">
      <Card className="divide-y divide-ink-100">
        {log.map((e) => (
          <div key={e.id} className="rise flex items-center gap-3 px-4 py-2.5 text-[12.5px]">
            <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${
              e.delta === 'up' ? 'bg-brand-500' : e.delta === 'down' ? 'bg-cool-500' : 'bg-ink-300'
            }`} />
            <span className="text-ink-700">{e.text}</span>
          </div>
        ))}
        <div className="px-4 py-2 text-[11px] text-ink-500">
          Basket now: {cart.reduce((a, l) => a + l.quantity, 0)} item{cart.reduce((a, l) => a + l.quantity, 0) === 1 ? '' : 's'} across {cart.length} line{cart.length === 1 ? '' : 's'}.
        </div>
      </Card>
    </Section>
  )
}
