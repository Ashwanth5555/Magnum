import { useEffect, useState } from 'react'
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Legend, Line,
  ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Truck, Thermometer, Trophy, Clock, PackageCheck } from 'lucide-react'
import { get, qs } from '../lib/api'
import { Ctx, ContextSel, StockAction } from '../lib/types'
import { deg, hourLabel, num, statusTone } from '../lib/format'
import { Card, ErrorNote, Section, Spinner, Stat } from '../components/ui'

const AXIS = { fontSize: 11, fill: '#6b6b6b' }
const TIP = { borderRadius: 12, border: '1px solid #eee', fontSize: 12 }

/* Four flavours, fixed order, fixed hues - a flavour keeps its colour when the
   store changes, so the eye tracks the same line across stores instead of
   re-learning the legend. Validated for colour-vision deficiency against the
   card surface; the chocolate brown for Classic is the one hue that also
   carries meaning. Amber is deliberately absent - it belongs to the
   temperature line. */
const FLAVOURS = [
  { key: 'classic', label: 'Classic', colour: '#854d0e' },
  { key: 'almond', label: 'Almond', colour: '#049e54' },
  { key: 'caramel', label: 'Caramel', colour: '#db2777' },
  { key: 'white', label: 'White chocolate', colour: '#2563eb' },
]

/* Which flavour a SKU belongs to, and a label short enough to sit under a
   column. The catalogue names ("Magnum Mini Classic Bars, 6 Count") are written
   for a shelf, not an axis. */
const SKU_META: Record<string, { flavour: string; short: string }> = {
  'MAG-CLS-1': { flavour: 'classic', short: 'Classic' },
  'MAG-ALM-1': { flavour: 'almond', short: 'Almond' },
  'MAG-CAR-1': { flavour: 'caramel', short: 'Caramel' },
  'MAG-WHT-1': { flavour: 'white', short: 'White' },
  'MAG-ALM-3': { flavour: 'almond', short: 'Almond 3ct' },
  'MAG-MIN-6': { flavour: 'classic', short: 'Mini 6ct' },
  'MAG-CAR-3': { flavour: 'caramel', short: 'Caramel 3ct' },
  'MAG-WHT-3': { flavour: 'white', short: 'White 3ct' },
}

/* Stock and demand are the two quantities every remaining chart compares, so
   they wear the same two colours everywhere: blue is what is physically on the
   shelf, green is what the peak will take, red is that same demand when the
   shelf cannot cover it. */
const C_STOCK = '#2563eb'
const C_DEMAND = '#049e54'
const C_SHORT = '#dc2626'

export default function DemandDesk({
  sel, ctx,
}: { sel: ContextSel; ctx: Ctx | null }) {
  const [network, setNetwork] = useState<any>(null)
  const [store, setStore] = useState<string | null>(null)
  const [detail, setDetail] = useState<any>(null)
  const [showMath, setShowMath] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const params = {
    day: sel.day, time_window: sel.time_window, season: sel.season, weather: sel.weather,
    game_day: sel.game_day, event: sel.event, activity: sel.activity,
  }

  useEffect(() => {
    get<any>(`/api/forecast/network?${qs(params)}`)
      .then((r) => {
        setNetwork(r)
        // Default to the store the scenario bar is standing in. Opening on the
        // riskiest store instead makes the header and the chart disagree.
        setStore((s) => s ?? ctx?.store_id ?? r.stores[0].store_id)
      })
      .catch(setError)
  }, [JSON.stringify(sel)])

  useEffect(() => {
    if (!store) return
    get<any>(`/api/forecast?${qs({ store_id: store, ...params })}`).then(setDetail).catch(setError)
  }, [store, JSON.stringify(sel)])

  if (error) return <ErrorNote error={error} />
  if (!network || !detail) return <Spinner label="Forecasting" />

  /* One column per hour, one field per flavour. The endpoint already returns a
     per-SKU series and the demand rate is fitted per store and SKU, so the mix
     genuinely shifts between stores - Greenwich runs whiter, Astoria runs more
     almond - rather than every store being the same curve rescaled. */
  const series = detail.total.map((h: any, i: number) => {
    const row: any = { ...h, label: hourLabel(h.hour) }
    for (const f of FLAVOURS) row[f.key] = 0
    for (const [sku, hours] of Object.entries<any>(detail.by_sku)) {
      const meta = SKU_META[sku]
      if (meta) row[meta.flavour] += hours[i]?.p50 ?? 0
    }
    for (const f of FLAVOURS) row[f.key] = Number(row[f.key].toFixed(2))
    return row
  })
  const peak = detail.peak
  const peakLabel = `${peak.day} ${hourLabel(peak.hour)}`
  const risk = network.stores.filter((s: any) => s.risk_skus > 0)

  // Two comparable quantities per SKU: what is on the shelf, and what the peak
  // will take. Everything else the endpoint returns is the arithmetic behind
  // those two, and it lives behind the toggle.
  const cover = detail.actions.map((a: StockAction) => ({
    sku_id: a.sku_id,
    short_name: SKU_META[a.sku_id]?.short ?? a.name.replace(/^Magnum /, ''),
    stock: a.on_hand + a.inbound,
    need: Number((a.forecast_p90_to_peak + a.safety_stock).toFixed(1)),
    short: a.gap < 0,
    gap: a.gap,
    on_hand: a.on_hand, inbound: a.inbound,
    p50: a.forecast_p50_to_peak, p90: a.forecast_p90_to_peak, safety: a.safety_stock,
    action_units: a.action_units,
    needed_by_offset_hours: a.needed_by_offset_hours,
  }))

  const netData = [...network.stores]
    .sort((x: any, y: any) => (y.risk_skus - x.risk_skus) || (x.on_hand - y.on_hand))
    .map((s_: any) => ({
      store_id: s_.store_id,
      label: `${s_.name.replace(/ Market$/, '')} — ${s_.state}`,
      name: s_.name, city: s_.city, state: s_.state, lead: s_.transfer_lead_minutes,
      on_hand: s_.on_hand,
      need: Number(s_.p90_to_peak.toFixed(1)),
      risk_skus: s_.risk_skus,
    }))

  return (
    <div className="space-y-7">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Network on hand" value={num(network.stores.reduce((a: number, s: any) => a + s.on_hand, 0))} hint="Magnum units across 10 stores" />
        <Stat label="Stores at risk" value={risk.length} tone={risk.length ? 'risk' : 'brand'} hint="p90 to peak exceeds cover" />
        <Stat label="Peak in" value={`${peak.offset}h`} hint={`${peak.day} ${hourLabel(peak.hour)} · ×${peak.demand_index.toFixed(2)}`} />
        <Stat label="Temperature" value={ctx ? deg(ctx.temperature_f) : '—'} hint={ctx ? `${ctx.temp_anomaly_f >= 0 ? '+' : ''}${ctx.temp_anomaly_f}°F vs ${ctx.season} norm` : ''} />
        <Stat label="Demand index" value={`×${ctx?.demand_index.toFixed(2)}`} tone="brand" hint="vs the same hour, ordinary conditions" />
      </div>

      <Section
        title="Next 48 hours, by flavour"
        subtitle={`${detail.store.name} · p50 units an hour for each Magnum flavour, from the shared context model. Every driver on the scenario bar moves these curves, and the mix underneath them is fitted per store — change the store and the flavours re-rank.`}
        right={
          <select value={store ?? ''} onChange={(e) => setStore(e.target.value)}
                  className="h-9 rounded-xl border border-ink-100 px-2.5 text-[13px] font-semibold outline-none hover:border-ink-300">
            {network.stores.map((s: any) => (
              <option key={s.store_id} value={s.store_id}>{s.name} — {s.state}</option>
            ))}
          </select>
        }
      >
        <Card className="p-4">
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={series} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#eee" vertical={false} />
              <XAxis dataKey="label" tick={AXIS} interval={3} tickLine={false} axisLine={false} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={TIP}
                formatter={(v: any, n: any) => [n === '°F' ? deg(Number(v)) : `${Number(v).toFixed(2)} units/h`, n]}
                labelFormatter={(l, p: any) => {
                  const d = p?.[0]?.payload
                  return d ? `${d.day} ${hourLabel(d.hour)} · ${deg(d.temperature_f)}` : l
                }}
              />
              {series.filter((s_: any) => s_.in_game_window).length > 0 && (
                <ReferenceArea
                  x1={series.find((s_: any) => s_.in_game_window)?.label}
                  x2={[...series].reverse().find((s_: any) => s_.in_game_window)?.label}
                  fill="#06c167" fillOpacity={0.07}
                />
              )}
              {/* Stacked, not four overlaid lines. Every flavour rides the same
                  hourly demand shape, so as lines they sit on top of each other
                  and the only thing worth seeing - how much of the hour each
                  flavour is - is the thing that disappears. Stacked, the top
                  edge is total demand and each band's thickness is that
                  flavour's share, which is what actually moves between stores. */}
              {FLAVOURS.map((f) => (
                <Area key={f.key} isAnimationActive={false} type="monotone" dataKey={f.key}
                      stackId="flavour" stroke={f.colour} strokeWidth={1} fill={f.colour}
                      fillOpacity={0.72} name={f.label} />
              ))}
              <Line isAnimationActive={false} type="monotone" dataKey="temperature_f" stroke="#d97706" strokeWidth={1.4} dot={false}
                    strokeDasharray="4 3" yAxisId="right" name="°F" />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#d97706' }}
                     tickLine={false} axisLine={false} width={34} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </ComposedChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11.5px] text-ink-500">
            <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> peak {peak.day} {hourLabel(peak.hour)}</span>
            {ctx?.in_game_window && <span className="flex items-center gap-1"><Trophy className="h-3 w-3 text-brand-600" /> shaded band is the game window</span>}
            <span className="flex items-center gap-1"><Thermometer className="h-3 w-3 text-warn-500" /> dashed amber is temperature, on the right axis</span>
            <span className="flex items-center gap-1"><Truck className="h-3 w-3" /> transfer lead {detail.store.transfer_lead_minutes} min</span>
          </div>
        </Card>
      </Section>

      <Section
        title="What to move, and by when"
        subtitle={`Every SKU at ${detail.store.name}. Blue is the stock actually on the shelf right now; green is the total demand the busiest hour ahead will actually take. Where the demand column is taller — and it turns red when it is — the shelf runs out before the peak.`}
        right={
          <button onClick={() => setShowMath((v) => !v)}
                  className="h-9 rounded-xl border border-ink-100 px-3 text-[12px] font-semibold text-ink-600 outline-none hover:border-ink-300">
            {showMath ? 'Hide the arithmetic' : 'Show the arithmetic'}
          </button>
        }
      >
        <Card className="p-4">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={cover} barGap={2} margin={{ top: 22, right: 8, bottom: 4, left: -18 }}>
              <CartesianGrid stroke="#eee" vertical={false} />
              <XAxis dataKey="short_name" tick={{ fontSize: 11, fill: '#2f2f2f' }}
                     tickLine={false} axisLine={false} interval={0} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TIP} cursor={{ fill: '#f7f7f7' }}
                       formatter={(v: any, n: any) => [`${Number(v).toFixed(1)} units`, n]} />
              <Legend verticalAlign="top" align="left" wrapperStyle={{ fontSize: 11, paddingBottom: 6 }} />
              <Bar isAnimationActive={false} dataKey="stock" name="Stock on the shelf now"
                   fill={C_STOCK} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="stock" position="top" style={{ fontSize: 10, fill: '#6b6b6b' }} />
              </Bar>
              <Bar isAnimationActive={false} dataKey="need" name="Total demand to the peak"
                   fill={C_DEMAND} radius={[4, 4, 0, 0]}>
                {cover.map((c: any) => (
                  <Cell key={c.sku_id} fill={c.short ? C_SHORT : C_DEMAND} />
                ))}
                <LabelList dataKey="need" position="top" style={{ fontSize: 10, fill: '#6b6b6b' }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* The chart says which SKUs are short. This says what to do about it,
              which is the only reason anybody opened the screen. */}
          <div className="mt-3 space-y-1.5 border-t border-ink-100 pt-3">
            {cover.filter((c: any) => c.short).length === 0 ? (
              <div className="flex items-center gap-1.5 text-[12.5px] text-ink-500">
                <PackageCheck className="h-3.5 w-3.5 text-brand-600" />
                Every SKU covers its peak. Nothing to move.
              </div>
            ) : cover.filter((c: any) => c.short).map((c: any) => (
              <div key={c.sku_id} className="flex flex-wrap items-baseline gap-x-2 text-[12.5px]">
                <Truck className="h-3.5 w-3.5 shrink-0 self-center text-risk-500" />
                <span className="font-semibold text-ink-900">{c.short_name}</span>
                <span className="text-risk-500">{units(Math.ceil(c.need - c.stock))} short by {peakLabel}</span>
                <span className="text-ink-500">
                  — move {units(c.action_units)}, van out within {c.needed_by_offset_hours.toFixed(1)}h
                </span>
              </div>
            ))}
          </div>

          {showMath && (
            <div className="mt-3 overflow-x-auto border-t border-ink-100 pt-3">
              <table className="w-full text-[11.5px] tabular-nums">
                <thead className="text-[10px] font-bold uppercase tracking-wider text-ink-500">
                  <tr>
                    <th className="py-1 pr-3 text-left">SKU</th>
                    <th className="px-2 py-1 text-right">On hand</th>
                    <th className="px-2 py-1 text-right">Inbound</th>
                    <th className="px-2 py-1 text-right">p50→peak</th>
                    <th className="px-2 py-1 text-right">p90→peak</th>
                    <th className="px-2 py-1 text-right">Safety</th>
                    <th className="pl-2 py-1 text-right">Gap</th>
                  </tr>
                </thead>
                <tbody className="text-ink-500">
                  {cover.map((c: any) => (
                    <tr key={c.sku_id}>
                      <td className="py-1 pr-3 text-left text-ink-900">{c.short_name}</td>
                      <td className="px-2 py-1 text-right">{c.on_hand}</td>
                      <td className="px-2 py-1 text-right">{c.inbound}</td>
                      <td className="px-2 py-1 text-right">{c.p50.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right">{c.p90.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right">{c.safety}</td>
                      <td className={`pl-2 py-1 text-right font-bold ${c.short ? 'text-risk-500' : 'text-brand-600'}`}>
                        {c.gap > 0 ? '+' : ''}{c.gap.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1.5 text-[11px] text-ink-500">
                gap = on hand + inbound − forecast p90 to peak − safety stock. Safety stock
                scales with the hour it protects rather than sitting at a flat number.
              </p>
            </div>
          )}
        </Card>
      </Section>

      <Section
          title="Across the network"
          subtitle="The same two quantities, one pair of columns per store: blue is the stock actually on its shelf, green is the total demand its own peak will take. Click a column to load that store's 48 hours above."
        >
          <Card className="p-4">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={netData} barGap={2} margin={{ top: 18, right: 8, bottom: 34, left: -18 }}>
                <CartesianGrid stroke="#eee" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#2f2f2f' }} interval={0}
                       angle={-32} textAnchor="end" height={54} tickLine={false} axisLine={false} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={TIP} cursor={{ fill: '#f7f7f7' }}
                         formatter={(v: any, n: any) => [`${Number(v).toFixed(1)} units`, n]}
                         labelFormatter={(l, p: any) => {
                           const d = p?.[0]?.payload
                           return d ? `${d.name} · ${d.city}, ${d.state} · ${d.lead} min away` : l
                         }} />
                <Legend verticalAlign="top" align="left" wrapperStyle={{ fontSize: 11, paddingBottom: 6 }} />
                <Bar isAnimationActive={false} dataKey="on_hand" name="Stock on the shelf now"
                     fill={C_STOCK} radius={[4, 4, 0, 0]} onClick={(d: any) => setStore(d.store_id)}
                     className="cursor-pointer">
                  {netData.map((d: any) => (
                    <Cell key={d.store_id} fill={C_STOCK}
                          fillOpacity={d.store_id === store ? 1 : 0.55} />
                  ))}
                </Bar>
                <Bar isAnimationActive={false} dataKey="need" name="Total demand to the peak"
                     fill={C_DEMAND} radius={[4, 4, 0, 0]} onClick={(d: any) => setStore(d.store_id)}
                     className="cursor-pointer">
                  {netData.map((d: any) => (
                    <Cell key={d.store_id} fill={d.risk_skus > 0 ? C_SHORT : C_DEMAND}
                          fillOpacity={d.store_id === store ? 1 : 0.55} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-2 text-[11.5px] leading-snug text-ink-500">
              A red demand column means that store has at least one SKU it cannot cover — it is
              borrowing, not lending. Sorted so the stores that need help are on the left and
              the ones with units to spare are on the right. The selected store is the solid pair.
            </p>
          </Card>
      </Section>

    </div>
  )
}

/** "1 unit", not "1 units" - the row is read out loud in a demo. */
const units = (n: number) => `${n} unit${n === 1 ? '' : 's'}`
