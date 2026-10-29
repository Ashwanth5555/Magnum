import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  BadgeCheck, Ban, BellRing, Clock, Lock, MapPin, Send, ShieldCheck, ShoppingBag,
  Tag, Timer, Users,
} from 'lucide-react'
import { get, post } from '../lib/api'
import { usd, pct, num, hourLabel } from '../lib/format'
import { Badge, Card, ErrorNote, Section, Spinner, Stat } from '../components/ui'
import ProductImage from '../components/ProductImage'
import { ContextSel } from '../lib/types'

const AXIS = { fontSize: 11, fill: '#6b7280' }

/* Seasons are banded behind the month-by-month chart rather than annotated on
   it: the shape of Magnum demand IS the season, so the reader should see the
   summer block before they read a single number. */
const SEASON_FILL: Record<string, string> = {
  Winter: '#eff6ff',
  Spring: '#f0fdf4',
  Summer: '#fffbeb',
  Autumn: '#fdf4f0',
}

/** Collapse the month rows into contiguous same-season runs, so each season is
 *  one band instead of three abutting rectangles with visible seams. */
function seasonBands(trend: any[]) {
  const runs: { season: string; from: string; to: string }[] = []
  for (const row of trend) {
    const last = runs[runs.length - 1]
    if (last && last.season === row.season) last.to = row.month
    else runs.push({ season: row.season, from: row.month, to: row.month })
  }
  /* A band drawn from its own first month to its own last month stops a whole
     category short of the next one, leaving unlabelled white gutters exactly
     where the season changes. Running each band up to the next band's first
     month makes them abut, so every point sits inside a season. */
  return runs.map((r, i) => ({ ...r, to: runs[i + 1]?.from ?? r.to }))
}

export default function Customer({
  customerId, onShop, sel,
}: { customerId: string | null; onShop: () => void; sel: ContextSel }) {
  const [d, setD] = useState<any>(null)
  const [n, setN] = useState<any>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    if (!customerId) { setD(null); return }
    let live = true
    setD(null); setError(null)
    get<any>(`/api/customer/${customerId}/analytics`)
      .then((r) => live && setD(r))
      .catch((e) => live && setError(e))
    return () => { live = false }
  }, [customerId])

  // The composed push is context-dependent in a way the rest of this screen is
  // not: the same household gets a different message on a 93-degree Friday than
  // on a wet Tuesday. So it refetches on the scenario, not just on the customer.
  useEffect(() => {
    if (!customerId) { setN(null); return }
    let live = true
    post<any>('/api/notify', { customer_id: customerId, context: sel, cart: [] })
      .then((r) => live && setN(r))
      .catch(() => live && setN(null))
    return () => { live = false }
  }, [customerId, JSON.stringify(sel)])

  if (!customerId) {
    return (
      <div className="rounded-2xl border border-dashed border-ink-100 py-20 text-center">
        <Users className="mx-auto mb-3 h-8 w-8 text-ink-300" />
        <div className="text-[15px] font-bold text-ink-900">Guest session</div>
        <p className="mx-auto mt-1 max-w-md text-[13px] leading-snug text-ink-500">
          Nothing to analyse — a guest has no history, which is exactly why the
          ranker moves that weight onto the weather and what is in stock. Pick a
          household from the selector to see what the system knows about them.
        </p>
      </div>
    )
  }
  if (error) return <ErrorNote error={error} />
  if (!d) return <Spinner label="Reading this household's log" />

  const id = d.identity
  const lt = d.lifetime
  const vs = d.versus_cluster
  const cad = d.cadence
  const el = d.eligibility

  return (
    <div className="space-y-7">
      {/* ---------------- identity ---------------- */}
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-4 border-b border-ink-100 bg-gradient-to-r from-brand-50 to-white px-5 py-4">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-ink-900 text-[17px] font-bold text-white">
            {id.display_name.split(' ').map((s: string) => s[0]).join('').slice(0, 2)}
          </span>
          <div className="min-w-0">
            <div className="text-[20px] font-bold tracking-tight text-ink-900">{id.display_name}</div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-ink-500">
              <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />
                {id.home_area.replace(/-/g, ' ')}, {id.state}</span>
              <span className="flex items-center gap-1"><ShoppingBag className="h-3.5 w-3.5" />
                home store {id.store_id}</span>
              <span className="font-mono text-[11px]">{d.customer_id}</span>
            </div>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Badge tone="brand">{id.cluster.name}</Badge>
            <Badge>{num(id.cluster.customers)} in this cluster</Badge>
            <Badge>peak {hourLabel(id.cluster.peak_hour)}</Badge>
            <button
              onClick={onShop}
              className="rounded-full bg-ink-900 px-3.5 py-1.5 text-[12px] font-bold text-white transition hover:bg-brand-500"
            >
              Shop as {id.display_name.split(' ')[0]}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3 text-[12px]">
          <span className="flex items-center gap-1.5 font-semibold">
            {el.consent_marketing
              ? <ShieldCheck className="h-4 w-4 text-brand-600" />
              : <Ban className="h-4 w-4 text-risk-500" />}
            Marketing consent {el.consent_marketing ? 'given' : 'withheld'}
          </span>
          <span className="flex items-center gap-1.5 font-semibold">
            {el.consent_personalisation
              ? <BadgeCheck className="h-4 w-4 text-brand-600" />
              : <Ban className="h-4 w-4 text-risk-500" />}
            Personalisation {el.consent_personalisation ? 'on' : 'off'}
          </span>
          <span className="text-ink-500">
            Contacts: {el.contacts_24h}/{el.cap_24h} in 24 h · {el.contacts_7d}/{el.cap_7d} in 7 d
          </span>
          {el.cap_hit && <Badge tone="risk">Frequency capped</Badge>}
          {el.suppressed && <Badge tone="warn">In {el.suppress_hours} h post-purchase suppression</Badge>}
          {!el.cap_hit && !el.suppressed && el.consent_marketing && (
            <Badge tone="brand">Contactable right now</Badge>
          )}
        </div>
      </Card>

      {/* ---------------- lifetime ---------------- */}
      <Section
        title="Lifetime with Magnum Now"
        subtitle={`Every number below is derived from this household's own rows in the log, as of ${d.as_of.slice(0, 10)}.`}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          <Stat label="Orders" value={num(lt.orders)}
                hint={`${num(lt.sessions)} sessions · ${pct(lt.session_to_order)} converted`} />
          <Stat label="Spend" value={usd(lt.spend, 0)} hint={`avg basket ${usd(lt.avg_basket)}`} />
          <Stat label="Margin" value={usd(lt.margin, 0)}
                hint={`${usd(lt.discount_taken)} given away in discount`} />
          <Stat label="Magnum orders" value={num(lt.magnum_orders)} tone="brand"
                hint={`${num(lt.magnum_units)} units · ${usd(lt.magnum_spend, 0)}`} />
          <Stat label="Attach rate" value={pct(vs.attach_rate.mine)}
                tone={vs.attach_rate.direction === 'above' ? 'brand' : 'neutral'}
                hint={`cluster ${pct(vs.attach_rate.cluster)}`} />
          <Stat label="Substitutions" value={pct(lt.substitution_rate)}
                hint="Share of orders where the first choice was out of stock" />
        </div>
      </Section>

      {/* ---------------- vs cluster ---------------- */}
      <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
        <Section
          title={`Against the ${id.cluster.short} cluster`}
          subtitle="A household number means nothing without its benchmark, so the two always travel together."
        >
          <Card className="divide-y divide-ink-100">
            {[
              ['Attach rate', vs.attach_rate, (v: number) => pct(v)],
              ['Units per Magnum order', vs.avg_units, (v: number) => v.toFixed(2)],
              ['Multipack share', vs.pack_share, (v: number) => pct(v)],
              ['Buys on discount', vs.discount_response, (v: number) => pct(v)],
            ].map(([label, v, fmt]: any) => {
              const span = Math.max(v.mine, v.cluster, 0.0001)
              return (
                <div key={label} className="px-4 py-3">
                  <div className="flex items-baseline justify-between text-[12.5px]">
                    <span className="font-semibold text-ink-900">{label}</span>
                    <span className="flex items-center gap-2 tabular-nums">
                      <span className="font-bold">{fmt(v.mine)}</span>
                      <span className="text-ink-500">vs {fmt(v.cluster)}</span>
                      <Badge tone={v.direction === 'above' ? 'brand' : v.direction === 'below' ? 'warn' : 'neutral'}>
                        {v.ratio ? `${v.ratio.toFixed(2)}×` : v.direction}
                      </Badge>
                    </span>
                  </div>
                  <div className="mt-2 space-y-1">
                    <div className="h-2 rounded-full bg-ink-50">
                      <div className="h-2 rounded-full bg-brand-500" style={{ width: `${(v.mine / span) * 100}%` }} />
                    </div>
                    <div className="h-2 rounded-full bg-ink-50">
                      <div className="h-2 rounded-full bg-ink-300" style={{ width: `${(v.cluster / span) * 100}%` }} />
                    </div>
                  </div>
                </div>
              )
            })}
            <div className="px-4 py-2.5 text-[11.5px] text-ink-500">
              Green is this household, grey is the wider group it resembles. That group is what
              the ranker falls back to when personal history is thin.
            </div>
          </Card>
        </Section>

        <Section
          title="When are they due?"
          subtitle="The reorder policy runs on the household's own rhythm, not a global cadence."
        >
          <Card className="p-5">
            <div className="flex items-end gap-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Due ratio</div>
                <div className={`text-4xl font-bold tabular-nums tracking-tight ${
                  cad.state === 'overdue' ? 'text-risk-500' : cad.state === 'due' ? 'text-brand-600' : 'text-ink-900'
                }`}>
                  {cad.due_ratio?.toFixed(2) ?? '—'}×
                </div>
              </div>
              <Badge tone={cad.state === 'overdue' ? 'risk' : cad.state === 'due' ? 'brand' : 'neutral'}>
                <Timer className="h-3 w-3" /> {cad.state}
              </Badge>
            </div>
            <p className="mt-1 text-[12.5px] text-ink-500">{cad.note}</p>

            <div className="mt-4 h-3 overflow-hidden rounded-full bg-ink-50">
              <div
                className={`h-3 rounded-full ${cad.state === 'overdue' ? 'bg-risk-500' : cad.state === 'due' ? 'bg-brand-500' : 'bg-ink-300'}`}
                style={{ width: `${Math.min(100, (cad.due_ratio ?? 0) * 80)}%` }}
              />
            </div>
            <div className="mt-1 flex justify-between text-[10.5px] text-ink-500">
              <span>just bought</span><span>0.85× — window opens</span><span>1.25× overdue</span>
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-[12.5px]">
              <dt className="text-ink-500">Own cadence</dt>
              <dd className="text-right font-semibold tabular-nums">{cad.cadence_days} days</dd>
              <dt className="text-ink-500">Cluster cadence</dt>
              <dd className="text-right font-semibold tabular-nums">{cad.cluster_cadence_days} days</dd>
              <dt className="text-ink-500">Days since Magnum</dt>
              <dd className="text-right font-semibold tabular-nums">{cad.days_since_magnum ?? '—'}</dd>
              <dt className="text-ink-500">Next due</dt>
              <dd className="text-right font-semibold tabular-nums">{cad.next_due_at?.slice(0, 10) ?? '—'}</dd>
              <dt className="text-ink-500">Usual hour</dt>
              <dd className="text-right font-semibold tabular-nums">{hourLabel(cad.usual_hour)}</dd>
            </dl>
          </Card>
        </Section>
      </div>

      {/* ---------------- mixes ---------------- */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Flavour mix" subtitle="This household's Magnum share by flavour, against their cluster's.">
          <Card className="p-4">
            <div style={{ height: 220 }}>
              <ResponsiveContainer>
                <BarChart data={d.flavour_mix} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="key" tick={AXIS} tickLine={false} axisLine={false} />
                  <YAxis tick={AXIS} tickLine={false} axisLine={false}
                         tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                  <Tooltip formatter={(v: any) => pct(Number(v))} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="mine" name="This household" fill="#06c167" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="cluster" name="Cluster" fill="#d1d5db" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Section>

        <Section title="What else they buy" subtitle="Category share of units — the basket the Magnum attaches to.">
          <Card className="p-4">
            <div className="space-y-2">
              {d.category_mix.slice(0, 7).map((c: any) => (
                <div key={c.key} className="flex items-center gap-3">
                  <span className="w-20 shrink-0 text-[12px] font-semibold capitalize text-ink-700">{c.key}</span>
                  <div className="h-3 flex-1 rounded-full bg-ink-50">
                    <div className={`h-3 rounded-full ${c.key === 'magnum' ? 'bg-brand-500' : 'bg-ink-300'}`}
                         style={{ width: `${c.mine * 100}%` }} />
                  </div>
                  <span className="w-12 text-right text-[12px] font-semibold tabular-nums">{pct(c.mine)}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 border-t border-ink-100 pt-3">
              <div className="mb-2 text-[11px] font-bold uppercase tracking-wide text-ink-500">Most bought SKUs</div>
              <div className="flex flex-wrap gap-1.5">
                {d.favourites.map((f: any) => (
                  <span key={f.sku_id}
                        className={`rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${
                          f.category === 'magnum' ? 'bg-brand-50 text-brand-700' : 'bg-ink-50 text-ink-700'}`}>
                    {f.name} · {f.units}
                  </span>
                ))}
              </div>
            </div>
          </Card>
        </Section>
      </div>

      {/* ---------------- rhythm ---------------- */}
      <Section title="Rhythm" subtitle="When this household actually orders. The reorder nudge is timed off these, not off a global send hour.">
        <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
          <Card className="p-4">
            <div className="mb-1 text-[12px] font-bold text-ink-900">Orders by hour</div>
            <div style={{ height: 180 }}>
              <ResponsiveContainer>
                <BarChart data={d.hours} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="hour" tick={AXIS} tickLine={false} axisLine={false}
                         tickFormatter={hourLabel} interval={2} />
                  <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip labelFormatter={(h: any) => hourLabel(Number(h))} />
                  <Bar dataKey="orders" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                    {d.hours.map((h: any) => (
                      <Cell key={h.hour} fill={h.hour === cad.usual_hour ? '#06c167' : '#d1d5db'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-[11.5px] text-ink-500">
              <Clock className="h-3.5 w-3.5" /> Green is their modal hour — {hourLabel(cad.usual_hour)}.
            </div>
          </Card>

          <Card className="p-4">
            <div className="mb-1 text-[12px] font-bold text-ink-900">Orders by weekday</div>
            <div style={{ height: 180 }}>
              <ResponsiveContainer>
                <BarChart data={d.days} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={false} />
                  <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="orders" fill="#111827" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      </Section>

      {/* ---------------- trend ---------------- */}
      <Section
        title="Magnum orders by season"
        subtitle="Magnum orders month by month across the window, banded by season. The line climbs into summer for almost every household — that is the whole thesis, one customer at a time."
      >
        <Card className="p-4">
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={d.trend} margin={{ top: 18, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                {seasonBands(d.trend).map((b) => (
                  <ReferenceArea
                    key={`${b.season}-${b.from}`}
                    x1={b.from}
                    x2={b.to}
                    fill={SEASON_FILL[b.season] ?? '#f9fafb'}
                    fillOpacity={1}
                    stroke="none"
                    label={{ value: b.season, position: 'insideTop', fontSize: 10, fill: '#9ca3af' }}
                  />
                ))}
                <XAxis dataKey="month" tick={AXIS} tickLine={false} axisLine={false} />
                {/* Headroom so the season labels along the top never sit under the
                    line, which for a rising seasonal curve is exactly where it ends up. */}
                <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false}
                       domain={[0, (max: number) => Math.ceil(max * 1.25) + 1]} />
                <Tooltip formatter={(v: any) => [v, 'Magnum orders']} />
                <Line type="monotone" dataKey="magnum_orders" name="Magnum orders" stroke="#06c167"
                      strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-ink-500">
            {['Autumn', 'Winter', 'Spring', 'Summer'].map((sname) => (
              <span key={sname} className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm border border-ink-100"
                      style={{ background: SEASON_FILL[sname] }} />
                {sname}
              </span>
            ))}
          </div>
        </Card>
      </Section>

      {/* ---------------- the nudge: everything above pays for it ---------- */}
      {n && <NotificationPanel n={n} />}

      {/* ---------------- recent orders ---------------- */}
      <Section title="Last ten orders">
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-[12.5px]">
            <thead className="bg-ink-50 text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                {['When', 'Store', 'Lines', 'Units', 'People', 'Intent', 'Magnum', 'Discount', 'Total', 'Split'].map((h) => (
                  <th key={h} className={`px-3 py-2 font-semibold ${['Lines', 'Units', 'People', 'Discount', 'Total'].includes(h) ? 'text-right' : 'text-left'}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {d.recent_orders.map((o: any) => (
                <tr key={o.order_id} className="hover:bg-ink-50/60">
                  <td className="px-3 py-2 tabular-nums">{o.ordered_at.slice(0, 16).replace('T', ' ')}</td>
                  <td className="px-3 py-2">{o.store_id}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{o.lines}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{o.units}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{o.people}</td>
                  <td className="px-3 py-2 text-ink-500">{o.intent_class}</td>
                  <td className="px-3 py-2">
                    {o.has_magnum
                      ? <span className="font-semibold text-brand-700">{o.magnum_name}</span>
                      : <span className="text-ink-300">—</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{o.discount > 0 ? usd(o.discount) : '—'}</td>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">{usd(o.total)}</td>
                  <td className="px-3 py-2"><Badge>{o.split}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </Section>

      <Card className="flex items-start gap-2 bg-ink-50/60 px-4 py-3 text-[12px] leading-relaxed text-ink-700">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-ink-500" />
        <span>{d.held_out}</span>
      </Card>
    </div>
  )
}

/**
 * The message this household would actually receive.
 *
 * Everything else on this screen is evidence; this is the thing the evidence
 * pays for. It is deliberately shown as a phone notification rather than a
 * table, because the question a client asks about a recommender is never "what
 * is the expected incremental margin" - it is "so what do you send, and when?"
 *
 * Three policies feed it and none of them are re-decided here: the reorder
 * model picks the hour, the pack model picks the size, the offer model picks
 * what rides along. When the guardrails say hold, the composed message is still
 * shown and visibly not sent, so the restraint is legible rather than invisible.
 */
function NotificationPanel({ n }: { n: any }) {
  const held = !n.send
  const off = n.offer
  return (
    <Section
      title="The nudge"
      subtitle="What this household would be sent, when, at what size, and with which offer attached. Composed from their cadence, the live context and the offer policy — not from a campaign calendar."
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        {/* -------- the phone -------- */}
        <div className="rounded-3xl border border-ink-100 bg-ink-900 p-3">
          <div className="mb-2 flex items-center justify-between px-1 text-[10px] font-semibold text-white/60">
            <span>{n.scheduled.label}</span>
            <span className="flex items-center gap-1">
              <BellRing className="h-3 w-3" /> Magnum Now
            </span>
          </div>
          <div className={`rounded-2xl bg-white/95 p-3 ${held ? 'opacity-60 grayscale' : ''}`}>
            <div className="flex gap-3">
              <ProductImage
                sku={n.product.sku_id} name={n.product.name}
                category={n.product.category} flavour={n.product.flavour}
                rounded="rounded-xl" className="h-14 w-14 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-bold leading-tight text-ink-900">
                  {n.message.title}
                </div>
                <p className="mt-1 text-[11.5px] leading-snug text-ink-700">{n.message.body}</p>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <span className="flex-1 rounded-full bg-brand-500 px-3 py-1.5 text-center text-[11.5px] font-bold text-white">
                {n.message.cta}
              </span>
              {off && (
                <span className="flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1.5 text-[11px] font-bold text-brand-700">
                  <Tag className="h-3 w-3" />
                  {off.discount_pct > 0 ? `${Math.round(off.discount_pct * 100)}% off` : 'offer'}
                </span>
              )}
            </div>
          </div>

          <div className={`mt-2.5 flex items-center gap-2 rounded-xl px-3 py-2 text-[11px] font-semibold ${
            held ? 'bg-white/10 text-white/70' : 'bg-brand-500/20 text-brand-200'
          }`}>
            {held ? <Ban className="h-3.5 w-3.5 shrink-0" /> : <Send className="h-3.5 w-3.5 shrink-0" />}
            <span className="leading-snug">
              {held
                ? `Composed, not sent — ${n.hold_copy ?? n.hold_reason}`
                : `Queued for ${n.scheduled.label}`}
            </span>
          </div>
        </div>

        {/* -------- the justification -------- */}
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Reorder odds, 7d" value={pct(n.probability_7d, 0)}
                  hint={`${Math.round(n.days_since_purchase)}d since · ${Math.round(n.cadence_days)}d cadence`} />
            <Stat label="Size" value={String(n.size.units_delivered)}
                  hint={`${n.size.q_raw?.toFixed?.(2) ?? '—'} bars before rounding → ${n.size.copy}`} />
            <Stat label="Offer attached" value={off ? (off.discount_pct > 0 ? `${Math.round(off.discount_pct * 100)}%` : 'free') : 'none'}
                  hint={off ? off.label : 'No discount paid for itself here'} />
            <Stat label="Expected net" value={usd(n.economics.expected_net, 2)}
                  hint={`${usd(n.economics.expected_gross_margin, 2)} margin − ${usd(n.economics.cost_to_send, 2)} to send`} />
          </div>

          <Card className="p-4">
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-ink-500">
              <Clock className="h-3.5 w-3.5" /> Why this hour
            </div>
            <p className="mt-1.5 text-[12.5px] leading-snug text-ink-700">{n.scheduled.why}</p>
          </Card>

          <Card className="p-4">
            <div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-ink-500">
              Why this household, why now
            </div>
            <ul className="space-y-2">
              {n.drivers.map((dr: any) => (
                <li key={dr.code} className="flex gap-2.5 text-[12.5px] leading-snug">
                  <span className={`mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full ${
                    dr.code === 'OVERDUE' || dr.code === 'DUE' ? 'bg-brand-500'
                      : dr.code === 'PERSONAL_FAVOURITE' ? 'bg-cool-500' : 'bg-warn-500'
                  }`} />
                  <span>
                    <span className="font-semibold text-ink-900">{dr.label}</span>
                    <span className="text-ink-500"> — {dr.detail}</span>
                  </span>
                </li>
              ))}
              {n.drivers.length === 0 && (
                <li className="text-[12.5px] text-ink-500">
                  Nothing about this household or this moment argues for a contact.
                </li>
              )}
            </ul>
            <p className="mt-3 border-t border-ink-100 pt-2.5 text-[11.5px] leading-snug text-ink-500">
              Whatever is doing the most work writes the headline. {n.message.lead_driver === 'CONTEXT_HEAT' || n.message.lead_driver === 'CONTEXT_MATCH'
                ? 'Here that is the weather, because this household is not yet due for a reorder.'
                : 'Here that is the household itself — being due to reorder outranks anything happening outside.'}
            </p>
          </Card>
        </div>
      </div>
    </Section>
  )
}
