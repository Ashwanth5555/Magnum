import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronDown, Link2, Minus, Plus, Sparkles, Tag, TicketX, Zap } from 'lucide-react'
import { Ranked } from '../lib/types'
import { usd } from '../lib/format'
import { Badge } from './ui'
import ProductImage from './ProductImage'

export type Signal = {
  code: string; label: string; value: string
  effect: number; direction: 'up' | 'down' | 'flat'; detail: string
}
type Contribution = { family: string; label?: string; weight: number; score: number; points: number }
export type Coupon = {
  has_coupon: boolean; kind: 'discount' | 'no_discount' | 'none'
  label: string | null; code: string | null
  discount_pct: number; base_discount_pct: number; saving: number
  why: string; slot: string | null; who: string | null; season_note: string
  depth_parts?: { conditions?: number; slot?: number; slot_index?: number }
}
type RailItem = Ranked & {
  rank: number; top_driver: string; top_driver_label?: string
  top_driver_points: number; in_results: boolean
  contributions: Contribution[]
  coupon?: Coupon
  pairing: {
    flavour: string; lift: number; units_ratio: number
    anchor_name: string | null; anchor_n: number | null; anchor_lift: number
    anchors: string[]
  } | null
}
export type Pairing = {
  active: boolean; weight: number
  anchors: { sku_id: string | null; name: string; source: string; n: number
             top_flavour: string; top_lift: number; units_ratio: number }[]
  flavour_pull: Record<string, number>
  top_flavour: string; top_lift: number
  units_ratio: number; baseline_units: number; baskets: number
}

/** Movement of one SKU between two consecutive recomputations. */
type Move = { rankDelta: number | null; scoreDelta: number }

/* Plain words, because the people this screen has to convince do not work on
   recommenders. A column headed "context" tells them nothing; "weather and time
   of day" tells them exactly what moved. The API sends the same labels, so the
   two can never drift apart. */
const DRIVER_LABEL: Record<string, string> = {
  personal: 'what they usually buy',
  peer: 'similar shoppers',
  context: 'the weather and the hour',
  availability: 'what is on the shelf',
  text: 'what they searched',
  pairing: 'what it goes with',
}
const DRIVER_DOT: Record<string, string> = {
  personal: 'bg-brand-500', peer: 'bg-brand-200',
  context: 'bg-warn-500', availability: 'bg-cool-500', text: 'bg-ink-300',
  pairing: 'bg-violet-500',
}
const FAMILY_BAR: Record<string, string> = {
  text: 'bg-ink-300', personal: 'bg-brand-500', peer: 'bg-brand-200',
  context: 'bg-warn-500', availability: 'bg-cool-500', pairing: 'bg-violet-500',
}

/**
 * The price this shopper would actually meet on this row.
 *
 * It is the same decision the cart makes, taken by the same function on the
 * same inputs, so the two surfaces cannot quote different numbers. It renders
 * in both directions on purpose: a system whose only visible behaviour is
 * handing out money is not a system anybody should trust with pricing, and the
 * hours where it declines are the ones worth showing a client.
 */
const pctTxt = (v: number | null | undefined) =>
  v == null ? '—' : `${Math.round(v * 100)}%`

/** One multiplier from the depth stack, signed so the direction reads at a glance. */
function DeltaChip({ label, v }: { label: string; v?: number }) {
  if (v == null || Math.abs(v) < 0.005) return null
  return (
    <span className="rounded-full bg-white/70 px-1.5 py-px">
      {label} {v > 0 ? '+' : '\u2212'}{Math.abs(v * 100).toFixed(1)}%
    </span>
  )
}

function RailCoupon({ c }: { c: Coupon }) {
  const disc = c.has_coupon && c.discount_pct > 0
  return (
    <div
      className={`mt-2 rounded-xl border px-2.5 py-2 ${
        disc ? 'border-brand-500/25 bg-brand-50' : 'border-ink-100 bg-ink-50/70'
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-white ${
            disc ? 'bg-brand-500' : 'bg-ink-300'
          }`}
        >
          {disc ? <Tag className="h-2.5 w-2.5" /> : <TicketX className="h-2.5 w-2.5" />}
        </span>
        <span
          className={`min-w-0 flex-1 truncate text-[11.5px] font-bold ${
            disc ? 'text-brand-700' : 'text-ink-600'
          }`}
          title={c.label ?? undefined}
        >
          {c.label ?? 'No coupon this hour'}
        </span>
        {disc && (
          <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[10.5px] font-bold tabular-nums text-brand-700">
            −{Math.round(c.discount_pct * 100)}%
          </span>
        )}
      </div>
      {disc && c.saving > 0 && (
        <div className="mt-1 text-[10.5px] font-semibold leading-snug text-brand-700/80">
          Saves {usd(c.saving)} — applied at checkout.
        </div>
      )}
      {/* Why this number and not the usual one. Two lines at most: what the
          hour did to the depth, then what this household did to it. */}
      {/* Three reasons, in the order they were applied: what the conditions did,
          what this slot in the week does on top, and what this household does on
          top of that. Each is a component and none of them claims to be the
          answer — the percentage on the right is the answer. Rounded to a whole
          percent two adjacent weekdays can print the same label, and these lines
          are where the difference between them stays visible. */}
      <div className={`mt-1 text-[10.5px] leading-snug ${disc ? 'text-brand-700/80' : 'text-ink-500'}`}>
        {c.why}
      </div>
      {c.slot && (
        <div className={`mt-0.5 text-[10.5px] leading-snug ${disc ? 'text-brand-700/70' : 'text-ink-500'}`}>{c.slot}</div>
      )}
      {c.who && (
        <div className={`mt-0.5 text-[10.5px] leading-snug ${disc ? 'text-brand-700/70' : 'text-ink-500'}`}>{c.who}</div>
      )}
      {disc && c.depth_parts && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 border-t border-brand-500/15 pt-1 text-[10px] tabular-nums text-brand-700/70">
          <span className="font-semibold">{pctTxt(c.base_discount_pct)} base</span>
          <DeltaChip label="hour" v={c.depth_parts.conditions} />
          <DeltaChip label="slot" v={c.depth_parts.slot} />
          <span className="font-bold text-brand-700">= {c.discount_pct != null ? (c.discount_pct * 100).toFixed(1) : '—'}%</span>
        </div>
      )}
    </div>
  )
}

/**
 * The persistent Magnum surface.
 *
 * It is ranked with the text term stood down, so it survives any query and any
 * category the shopper browses into - which is the whole point: the moment a
 * shopper searches "wings" is exactly the moment a Magnum stakeholder wants to
 * know what the system would place.
 *
 * Every recomputation is diffed against the previous one, so the rail shows not
 * just the current answer but what the last change did to it.
 */
export default function LiveRecoRail({
  items, signals, latency, personalised, who, onAdd, trigger, pairing,
}: {
  items: RailItem[]
  signals: Signal[]
  pairing: Pairing | null
  latency: number
  personalised: boolean
  who: string
  onAdd: (sku: string) => void
  /** Anything that, when it changes, means "this is a new computation". */
  trigger: string
}) {
  const [openSku, setOpenSku] = useState<string | null>(null)
  const prev = useRef<Record<string, { rank: number; score: number }>>({})
  const [moves, setMoves] = useState<Record<string, Move>>({})
  const [flash, setFlash] = useState(0)
  const lastTrigger = useRef(trigger)

  useEffect(() => {
    if (!items.length) return
    const before = prev.current
    const next: Record<string, Move> = {}
    for (const it of items) {
      const b = before[it.sku_id]
      next[it.sku_id] = {
        rankDelta: b ? b.rank - it.rank : null,
        scoreDelta: b ? it.match_score - b.score : 0,
      }
    }
    // Only treat it as a *move* when the inputs actually changed. A re-render
    // with the same context is not news and must not blink the rail.
    if (lastTrigger.current !== trigger) {
      setMoves(next)
      setFlash((f) => f + 1)
      lastTrigger.current = trigger
    }
    prev.current = Object.fromEntries(
      items.map((i) => [i.sku_id, { rank: i.rank, score: i.match_score }]),
    )
  }, [items, trigger])

  const changed = Object.values(moves).some((m) => (m.rankDelta ?? 0) !== 0)

  return (
    <aside className="order-1 xl:order-2 xl:sticky xl:top-4">
      <div className="overflow-hidden rounded-2xl border border-ink-100 bg-white">
        <div className="flex items-center gap-2 border-b border-ink-100 bg-gradient-to-r from-brand-50 to-white px-4 py-3">
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand-500 text-white">
            <Sparkles className="h-4 w-4" />
          </span>
          <div className="min-w-0 leading-tight">
            <div className="text-[14px] font-bold tracking-tight">Live Magnum picks</div>
            <div className="truncate text-[11px] text-ink-500">
              {personalised ? `Ranked for ${who}` : 'Guest session — weather and stock only'}
            </div>
          </div>
          <span
            key={flash}
            className="pulse ml-auto flex shrink-0 items-center gap-1 rounded-full bg-ink-900 px-2 py-1 text-[10px] font-bold text-white tabular-nums"
            title="Measured server time for this recomputation"
          >
            <Zap className="h-3 w-3" /> {latency} ms
          </span>
        </div>

        <div className="border-b border-ink-100 px-4 py-2 text-[11px] text-ink-500">
          Ranked independently of the search box — this is what the system would
          place for Magnum right now, whatever the shopper is looking at.
        </div>

        {pairing && <PairingNote p={pairing} />}

        <ol className="divide-y divide-ink-100">
          {items.map((p) => {
            const m = moves[p.sku_id]
            const rd = m?.rankDelta ?? null
            const out = p.stock_state === 'out_of_stock'
            return (
              <li key={p.sku_id} className="px-3 py-2.5">
                <div className="flex gap-3">
                <span className="relative h-11 w-11 shrink-0">
                  <ProductImage sku={p.sku_id} name={p.name} category={p.category} flavour={p.flavour} rounded="rounded-lg" className="h-11 w-11" />
                  <span className="absolute -left-1 -top-1 z-10 grid h-4 w-4 place-items-center rounded-full bg-ink-900 text-[9px] font-bold text-white tabular-nums">
                    {p.rank}
                  </span>
                </span>

                <div className="min-w-0 flex-1">
                  <div className="line-clamp-2 text-[12.5px] font-bold leading-tight text-ink-900" title={p.name}>
                    {p.name}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-500">
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DRIVER_DOT[p.top_driver]}`} />
                    <span className="truncate">{DRIVER_LABEL[p.top_driver] ?? p.top_driver_label ?? p.top_driver}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px]">
                    <span className="font-bold tabular-nums text-ink-900">{usd(p.price)}</span>
                    <span className="tabular-nums text-ink-500">{p.match_score.toFixed(3)}</span>
                    {rd === null ? (
                      <Badge tone="brand" className="!px-1.5 !py-0">new</Badge>
                    ) : rd > 0 ? (
                      <span className="flex items-center font-bold text-brand-600 tabular-nums">
                        <ArrowUp className="h-3 w-3" />{rd}
                      </span>
                    ) : rd < 0 ? (
                      <span className="flex items-center font-bold text-risk-500 tabular-nums">
                        <ArrowDown className="h-3 w-3" />{-rd}
                      </span>
                    ) : (
                      <Minus className="h-3 w-3 text-ink-300" />
                    )}
                    {out && <span className="font-semibold text-risk-500">sold out</span>}
                  </div>
                </div>

                <div className="flex shrink-0 flex-col items-center gap-1 self-start">
                  <button
                    onClick={() => !out && onAdd(p.sku_id)}
                    disabled={out}
                    title={out ? 'Out of stock' : 'Add to cart'}
                    className="mt-1 grid h-7 w-7 place-items-center rounded-full bg-ink-900 text-white transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:bg-ink-100 disabled:text-ink-300"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setOpenSku(openSku === p.sku_id ? null : p.sku_id)}
                    title="Score breakdown"
                    className={`grid h-5 w-5 place-items-center rounded-full text-ink-500 transition hover:bg-ink-100 ${
                      openSku === p.sku_id ? 'rotate-180 bg-ink-100' : ''
                    }`}
                  >
                    <ChevronDown className="h-3 w-3" />
                  </button>
                </div>
                </div>

                {/* The score, as a shape before it is a number. A stacked bar
                    answers "which factor put it here" at a glance; the numbers
                    behind it are one click away for anyone who wants them. */}
                <div className="mt-2 flex h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                  {p.contributions.map((c) => (
                    <span
                      key={c.family}
                      title={`${c.label ?? c.family}: ${c.points.toFixed(3)} of ${p.match_score.toFixed(3)}`}
                      className={FAMILY_BAR[c.family]}
                      style={{ width: `${(c.points / p.match_score) * 100}%` }}
                    />
                  ))}
                </div>

                {p.coupon && <RailCoupon c={p.coupon} />}

                {openSku === p.sku_id && (
                  <div className="rise mt-2 rounded-xl bg-ink-50 p-2.5">
                    <table className="w-full text-[10.5px]">
                      <thead className="text-[9px] font-bold uppercase tracking-wider text-ink-500">
                        <tr>
                          <th className="pb-1 text-left">What moved it</th>
                          <th className="pb-1 text-right">Score</th>
                          <th className="pb-1 text-right">Weight</th>
                          <th className="pb-1 text-right">Points</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...p.contributions].sort((a, b) => b.points - a.points).map((c) => (
                          <tr key={c.family}>
                            <td className="py-0.5">
                              <span className="flex items-center gap-1.5">
                                <span className={`h-1.5 w-1.5 rounded-full ${FAMILY_BAR[c.family]}`} />
                                {c.label ?? c.family}
                              </span>
                            </td>
                            <td className="py-0.5 text-right tabular-nums text-ink-500">{c.score.toFixed(2)}</td>
                            <td className="py-0.5 text-right tabular-nums text-ink-500">{c.weight.toFixed(2)}</td>
                            <td className="py-0.5 text-right font-bold tabular-nums">{c.points.toFixed(3)}</td>
                          </tr>
                        ))}
                        <tr className="border-t border-ink-200">
                          <td className="pt-1 font-bold" colSpan={3}>Match score</td>
                          <td className="pt-1 text-right font-bold tabular-nums">{p.match_score.toFixed(3)}</td>
                        </tr>
                      </tbody>
                    </table>
                    {p.pairing && (
                      <p className="mt-2 border-t border-ink-200 pt-2 text-[10.5px] leading-snug text-ink-700">
                        <span className="font-semibold text-violet-700">Pairing:</span>{' '}
                        {p.pairing.anchor_name
                          ? `baskets with ${p.pairing.anchor_name} take ${p.pairing.flavour} `
                          : `this basket takes ${p.pairing.flavour} `}
                        <span className="font-bold tabular-nums">{p.pairing.anchor_lift.toFixed(2)}×</span>
                        {' '}more often than average
                        {p.pairing.anchor_n ? `, across ${p.pairing.anchor_n.toLocaleString()} baskets` : ''}.
                      </p>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ol>

        <div className="border-t border-ink-100 bg-ink-50/60 px-4 py-3">
          <div className="mb-2 text-[11px] font-bold uppercase tracking-wide text-ink-500">
            What is moving this list
          </div>
          <ul className="space-y-1.5">
            {signals.map((s) => (
              <li key={s.code} className="flex items-start gap-2 text-[11.5px] leading-snug" title={s.detail}>
                <span
                  className={`mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full ${
                    s.direction === 'up' ? 'bg-brand-500' : s.direction === 'down' ? 'bg-risk-500' : 'bg-ink-300'
                  }`}
                />
                <span className="flex-1 text-ink-700">
                  <span className="font-semibold text-ink-900">{s.label}</span> {s.value}
                </span>
                <span
                  className={`shrink-0 font-bold tabular-nums ${
                    s.effect > 0 ? 'text-brand-600' : s.effect < 0 ? 'text-risk-500' : 'text-ink-500'
                  }`}
                >
                  {s.effect > 0 ? '+' : ''}{s.effect.toFixed(2)}
                </span>
              </li>
            ))}
            {signals.length === 0 && (
              <li className="text-[11.5px] text-ink-500">
                Neutral context — nothing is pushing the ranking away from the baseline.
              </li>
            )}
          </ul>
          {changed && (
            <div className="rise mt-2 border-t border-ink-100 pt-2 text-[11px] font-semibold text-brand-700">
              The last change re-ordered this rail.
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}

/**
 * What the pairing term is currently keyed to.
 *
 * This is the answer to "why did the list change when I searched for pizza",
 * and it has to carry its evidence: the flavour it pulls toward, how hard, how
 * many bars the basket tends to take, and the number of real baskets that claim
 * rests on. A pairing panel without the basket count is a merchandiser's
 * opinion wearing a lab coat.
 */
function PairingNote({ p }: { p: Pairing }) {
  const pull = Object.entries(p.flavour_pull).sort((a, b) => b[1] - a[1])
  const bigger = p.units_ratio >= 1.08
  const smaller = p.units_ratio <= 0.92
  return (
    <div className="border-b border-violet-500/20 bg-violet-50/60 px-4 py-3">
      <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-violet-700">
        <Link2 className="h-3 w-3" /> Pairing is live · {(p.weight * 100).toFixed(0)}% of the score
      </div>

      <p className="mt-1.5 text-[11.5px] leading-snug text-ink-700">
        Matched against <span className="font-semibold text-ink-900">{p.anchors.map((a) => a.name).join(', ')}</span>.
        Baskets like this take <span className="font-bold text-violet-700">{p.top_flavour}</span>{' '}
        <span className="font-bold tabular-nums">{p.top_lift.toFixed(2)}×</span> more often than the store average,
        measured across <span className="font-semibold tabular-nums">{p.baskets.toLocaleString()}</span> real baskets.
      </p>

      <div className="mt-2 space-y-1">
        {pull.map(([f, v]) => (
          <div key={f} className="flex items-center gap-2 text-[10.5px]">
            <span className="w-14 shrink-0 text-ink-500">{f}</span>
            <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-white">
              {/* 1.0x is "no information", so the bar grows from the midpoint in
                  whichever direction the evidence actually points. */}
              <span
                className={`absolute top-0 h-full ${v >= 1 ? 'bg-violet-500' : 'bg-ink-300'}`}
                style={{
                  left: v >= 1 ? '50%' : `${50 - Math.min(50, (1 - v) * 55)}%`,
                  width: `${Math.min(50, Math.abs(v - 1) * 55)}%`,
                }}
              />
              <span className="absolute left-1/2 top-0 h-full w-px bg-ink-200" />
            </span>
            <span className={`w-10 shrink-0 text-right font-bold tabular-nums ${
              v >= 1.15 ? 'text-violet-700' : v <= 0.85 ? 'text-ink-400' : 'text-ink-500'
            }`}>
              {v.toFixed(2)}×
            </span>
          </div>
        ))}
      </div>

      {(bigger || smaller) && (
        <p className="mt-2 border-t border-violet-500/20 pt-2 text-[11px] leading-snug text-ink-700">
          <span className="font-semibold text-ink-900">Size follows too.</span>{' '}
          These baskets carry <span className="font-bold tabular-nums">{p.units_ratio.toFixed(2)}×</span>{' '}
          the bars of an average one
          {p.baseline_units ? ` (${(p.baseline_units * p.units_ratio).toFixed(1)} against ${p.baseline_units.toFixed(1)})` : ''}
          {bigger ? ' — so packs rank above singles.' : ' — a single-serve meal, so singles rank above packs.'}
        </p>
      )}
    </div>
  )
}
