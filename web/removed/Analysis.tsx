import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, ErrorBar, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { CheckCircle2, XCircle, ShieldAlert, Lock } from 'lucide-react'
import { get } from '../lib/api'
import { num, pct, usd } from '../lib/format'
import { Badge, Card, ErrorNote, Section, Spinner, Stat } from '../components/ui'

const TABS = [
  { id: 'uplift', label: 'Incremental lift' },
  { id: 'policy', label: 'Policy value' },
  { id: 'forecast', label: 'Forecast accuracy' },
  { id: 'drivers', label: 'Demand drivers' },
  { id: 'validation', label: 'Validation' },
] as const

export default function Analysis({ meta }: { meta: any }) {
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('uplift')
  const [ov, setOv] = useState<any>(null)
  const [d, setD] = useState<Record<string, any>>({})
  const [error, setError] = useState<unknown>(null)

  useEffect(() => { get<any>('/api/analysis/overview').then(setOv).catch(setError) }, [])
  useEffect(() => {
    const path: Record<string, string> = {
      uplift: '/api/analysis/uplift?split=all', policy: '/api/analysis/policy-eval',
      forecast: '/api/analysis/forecast-accuracy', drivers: '/api/analysis/demand-drivers',
      validation: '/api/analysis/validation',
    }
    if (!d[tab]) get<any>(path[tab]).then((r) => setD((s) => ({ ...s, [tab]: r }))).catch(setError)
  }, [tab])

  if (error) return <ErrorNote error={error} />
  if (!ov) return <Spinner label="Loading the log" />

  return (
    <div className="space-y-7">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label="Sessions" value={num(ov.sessions)} />
        <Stat label="Orders" value={num(ov.orders)} hint={`${pct(ov.session_to_order)} of sessions`} />
        <Stat label="Magnum attach" value={pct(ov.attach_rate)} tone="brand" hint={`${num(ov.magnum_units)} units`} />
        <Stat label="Avg basket" value={usd(ov.avg_basket)} />
        <Stat label="Stockout hours" value={pct(ov.stockout_rate)} hint={`${num(ov.waste_units)} units wasted`} />
        <Stat label="Decisions logged" value={num(meta.row_counts.offers)} hint={`${num(meta.uplift_fit_rows)} in the fit split`} />
      </div>

      <div className="flex flex-wrap gap-2 border-b border-ink-100 pb-3">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`rounded-full px-3.5 py-2 text-[13px] font-semibold transition ${
              tab === t.id ? 'bg-ink-900 text-white' : 'text-ink-500 hover:bg-ink-50'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {!d[tab] && <Spinner />}
      {tab === 'uplift' && d.uplift && <Uplift d={d.uplift} />}
      {tab === 'policy' && d.policy && <Policy d={d.policy} />}
      {tab === 'forecast' && d.forecast && <Forecast d={d.forecast} />}
      {tab === 'drivers' && d.drivers && <Drivers d={d.drivers} ov={ov} />}
      {tab === 'validation' && d.validation && <Validation d={d.validation} meta={meta} />}
    </div>
  )
}

function Uplift({ d }: { d: any }) {
  const arms = d.arms.filter((a: any) => a.arm !== 'none')
  const chart = arms.map((a: any) => ({
    ...a, err: [a.uplift_pp - a.ci_low_pp, a.ci_high_pp - a.uplift_pp],
  }))
  return (
    <div className="space-y-6">
      <Section title="Volume versus money"
               subtitle={`${num(d.n_decisions)} randomised decisions. Arms were assigned uniformly at 20% each, so a difference of means is an unbiased estimate — no model stands between the log and this chart.`}>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-4">
            <h3 className="mb-3 text-[13px] font-bold">Attach lift vs no contact (95% CI)</h3>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={chart} margin={{ left: -20, right: 8 }}>
                <CartesianGrid stroke="#eee" vertical={false} />
                <XAxis dataKey="arm" tick={{ fontSize: 10, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} unit="pp" />
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #eee', fontSize: 12 }} />
                <ReferenceLine y={0} stroke="#b3b3b3" />
                <Bar isAnimationActive={false} dataKey="uplift_pp" radius={[6, 6, 0, 0]} name="uplift">
                  {chart.map((c: any, i: number) => (
                    <Cell key={i} fill={c.significant ? '#06c167' : '#b3b3b3'} />
                  ))}
                  <ErrorBar dataKey="err" width={5} strokeWidth={1.5} stroke="#2f2f2f" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-1 text-[11.5px] text-ink-500">
              {chart.every((c: any) => c.significant)
                ? 'Every interval clears zero: at this sample size all four nudges genuinely lift attach.'
                : 'Grey bars are not distinguishable from zero at this sample size.'}
            </p>
          </Card>

          <Card className="p-4">
            <h3 className="mb-3 text-[13px] font-bold">Contribution per decision vs no contact</h3>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={chart} margin={{ left: -20, right: 8 }}>
                <CartesianGrid stroke="#eee" vertical={false} />
                <XAxis dataKey="arm" tick={{ fontSize: 10, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #eee', fontSize: 12 }}
                         formatter={(v: any) => usd(Number(v), 4)} />
                <ReferenceLine y={0} stroke="#b3b3b3" />
                <Bar isAnimationActive={false} dataKey="reward_vs_none" radius={[6, 6, 0, 0]} name="$ vs none">
                  {chart.map((c: any, i: number) => (
                    <Cell key={i} fill={c.reward_vs_none >= 0 ? '#06c167' : '#dc2626'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-1 text-[11.5px] text-ink-500">
              Reward = Magnum unit margin − discount given − contact cost.
            </p>
          </Card>
        </div>
      </Section>

      <Card className="overflow-hidden">
        <table className="w-full text-[12.5px]">
          <thead className="bg-ink-50 text-[10px] font-bold uppercase tracking-wider text-ink-500">
            <tr>
              <th className="px-4 py-2.5 text-left">Arm</th>
              <th className="px-3 py-2.5 text-right">Decisions</th>
              <th className="px-3 py-2.5 text-right">Attach</th>
              <th className="px-3 py-2.5 text-right">Uplift</th>
              <th className="px-3 py-2.5 text-right">95% CI</th>
              <th className="px-3 py-2.5 text-right">Discount</th>
              <th className="px-3 py-2.5 text-right">Contact</th>
              <th className="px-4 py-2.5 text-right">$ vs none</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {d.arms.map((a: any) => (
              <tr key={a.arm} className={a.arm === 'none' ? 'bg-ink-50/50' : ''}>
                <td className="px-4 py-2.5 font-semibold">{a.arm}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-ink-500">{num(a.n)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{pct(a.attach_rate)}</td>
                <td className="px-3 py-2.5 text-right font-bold tabular-nums">
                  {a.arm === 'none' ? '—' : `${a.uplift_pp >= 0 ? '+' : ''}${a.uplift_pp.toFixed(2)}pp`}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-ink-500">
                  {a.arm === 'none' ? '—' : `[${a.ci_low_pp.toFixed(2)}, ${a.ci_high_pp.toFixed(2)}]`}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-ink-500">{usd(a.discount_cost_per_decision, 3)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-ink-500">{usd(a.contact_cost_per_decision, 3)}</td>
                <td className={`px-4 py-2.5 text-right font-bold tabular-nums ${
                  a.arm === 'none' ? 'text-ink-300' : a.reward_vs_none >= 0 ? 'text-brand-600' : 'text-risk-500'}`}>
                  {a.arm === 'none' ? '—' : usd(a.reward_vs_none, 4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-[12px] leading-relaxed text-ink-500">{d.note}</p>
    </div>
  )
}

function Policy({ d }: { d: any }) {
  const chart = d.policies.map((p: any) => ({
    ...p, err: [p.value_per_decision - p.ci_low, p.ci_high - p.value_per_decision],
  }))
  return (
    <div className="space-y-6">
      <Section title="What each policy would have been worth"
               subtitle={`${d.estimator}. Scored on ${num(d.n_decisions)} held-out decisions — no policy sees data it was fitted on.`}>
        <Card className="p-4">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chart} layout="vertical" margin={{ left: 40, right: 24 }}>
              <CartesianGrid stroke="#eee" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="policy" width={130} tick={{ fontSize: 11, fill: '#2f2f2f' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #eee', fontSize: 12 }}
                       formatter={(v: any) => usd(Number(v), 4)} />
              <Bar isAnimationActive={false} dataKey="value_per_decision" radius={[0, 6, 6, 0]}>
                {chart.map((c: any, i: number) => (
                  <Cell key={i} fill={c.policy === 'eic_greedy_v1' ? '#06c167' : c.policy === 'do_nothing' ? '#b3b3b3' : '#2f2f2f'} />
                ))}
                <ErrorBar dataKey="err" width={5} strokeWidth={1.5} stroke="#6b6b6b" direction="x" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </Section>

      <Card className="overflow-hidden">
        <table className="w-full text-[12.5px]">
          <thead className="bg-ink-50 text-[10px] font-bold uppercase tracking-wider text-ink-500">
            <tr>
              <th className="px-4 py-2.5 text-left">Policy</th>
              <th className="px-3 py-2.5 text-right">$ / decision</th>
              <th className="px-3 py-2.5 text-right">95% CI</th>
              <th className="px-3 py-2.5 text-right">Attach</th>
              <th className="px-3 py-2.5 text-right">Matched</th>
              <th className="px-4 py-2.5 text-left">Arm mix</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {d.policies.map((p: any) => (
              <tr key={p.policy} className={p.policy === 'eic_greedy_v1' ? 'bg-brand-50/50' : ''}>
                <td className="px-4 py-2.5 font-semibold">
                  {p.policy}
                  {p.policy === 'eic_greedy_v1' && <Badge tone="brand" className="ml-2">shipped V1</Badge>}
                </td>
                <td className="px-3 py-2.5 text-right font-bold tabular-nums">{usd(p.value_per_decision, 4)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-ink-500">
                  [{p.ci_low.toFixed(3)}, {p.ci_high.toFixed(3)}]
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">{pct(p.attach_rate)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums text-ink-500">{num(p.matched_decisions)}</td>
                <td className="px-4 py-2.5">
                  <div className="flex h-2.5 w-40 overflow-hidden rounded-full bg-ink-50">
                    {Object.entries(p.arm_mix as Record<string, number>).map(([k, v]) => (
                      <div key={k} title={`${k} ${pct(v, 0)}`} style={{ width: `${v * 100}%` }}
                           className={{ none: 'bg-ink-300', reminder: 'bg-brand-200', flavour_discovery: 'bg-brand-400',
                                        multipack_value: 'bg-brand-600', voucher20: 'bg-risk-500' }[k] ?? 'bg-ink-300'} />
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card className="flex gap-3 border-warn-500/20 bg-warn-50 p-4">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn-500" />
        <p className="text-[12.5px] leading-relaxed text-ink-700">
          <strong>The result worth arguing about.</strong> <code>uplift_greedy</code> maximises the objective a
          conversion model optimises — it correctly finds the voucher's real lift and hands it to almost everyone —
          and lands second from last on money. Chasing incremental conversions and chasing incremental profit are
          different problems, and only one of them pays for the discount.
        </p>
      </Card>
      <p className="text-[12px] leading-relaxed text-ink-500">{d.note}</p>
    </div>
  )
}

function Forecast({ d }: { d: any }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="p90 coverage" value={pct(d.coverage_p90)} tone="brand" hint="hours the shelf would have survived" />
        <Stat label="WAPE store-day" value={d.wape_store_day.toFixed(2)} hint="units per store per day" />
        <Stat label="WAPE SKU-day" value={d.wape_sku_day.toFixed(2)} />
        <Stat label="Pinball @ p90" value={d.pinball_p90.toFixed(3)} />
        <Stat label="Bias" value={`${d.bias_units_per_hour >= 0 ? '+' : ''}${d.bias_units_per_hour.toFixed(3)}`} hint="units/hour" />
      </div>

      <Section title="Forecast against actuals"
               subtitle={`${num(d.n_pairs)} pairs from ${d.origins} weekly backtest origins, each looking 48 hours ahead using only sales that had already happened.`}>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-4">
            <h3 className="mb-3 text-[13px] font-bold">Daily totals</h3>
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={d.timeseries} margin={{ left: -20, right: 8 }}>
                <CartesianGrid stroke="#eee" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b6b6b' }} axisLine={false} tickLine={false}
                       interval={Math.max(0, Math.floor(d.timeseries.length / 8))}
                       tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #eee', fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="actual" stroke="#0b0b0b" strokeWidth={2} dot={false} />
                <Line isAnimationActive={false} type="monotone" dataKey="forecast" stroke="#06c167" strokeWidth={2} strokeDasharray="5 3" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card className="p-4">
            <h3 className="mb-3 text-[13px] font-bold">Predicted vs actual, SKU-day</h3>
            <ResponsiveContainer width="100%" height={230}>
              <ScatterChart margin={{ left: -20, right: 8 }}>
                <CartesianGrid stroke="#eee" />
                <XAxis type="number" dataKey="p50" name="forecast" tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
                <YAxis type="number" dataKey="units" name="actual" tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
                <ZAxis range={[18, 18]} />
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #eee', fontSize: 12 }} cursor={{ strokeDasharray: '3 3' }} />
                <Scatter isAnimationActive={false} data={d.scatter} fill="#06c167" fillOpacity={0.45} />
              </ScatterChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="overflow-hidden">
          <div className="border-b border-ink-100 px-4 py-2.5 text-[13px] font-bold">By horizon</div>
          <table className="w-full text-[12.5px]">
            <thead className="bg-ink-50 text-[10px] font-bold uppercase tracking-wider text-ink-500">
              <tr><th className="px-4 py-2 text-left">Ahead</th><th className="px-3 py-2 text-right">p90 coverage</th><th className="px-3 py-2 text-right">Actual units</th></tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {d.by_horizon.map((h: any) => (
                <tr key={h.horizon_bucket}>
                  <td className="px-4 py-2 font-semibold">{h.label}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{pct(h.coverage_p90)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-500">{num(h.actual_units)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card className="overflow-hidden">
          <div className="border-b border-ink-100 px-4 py-2.5 text-[13px] font-bold">By SKU</div>
          <table className="w-full text-[12.5px]">
            <thead className="bg-ink-50 text-[10px] font-bold uppercase tracking-wider text-ink-500">
              <tr><th className="px-4 py-2 text-left">SKU</th><th className="px-3 py-2 text-right">WAPE day</th><th className="px-3 py-2 text-right">Coverage</th></tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {d.by_sku.map((s: any) => (
                <tr key={s.sku_id}>
                  <td className="px-4 py-2 font-semibold">{s.name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.wape_sku_day.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-500">{pct(s.coverage_p90)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      <p className="text-[12px] leading-relaxed text-ink-500">{d.note}</p>
    </div>
  )
}

function Drivers({ d, ov }: { d: any; ov: any }) {
  const temp = d.temperature.map((t: any) => ({ ...t, bucket: t.temperature_f, attach_pct: t.attach * 100 }))
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Hot vs cold attach" value={`${d.headline.hot_vs_cold_ratio}×`} tone="brand"
              hint={`${pct(d.headline.hot_vs_cold_attach[0])} above 80°F vs ${pct(d.headline.hot_vs_cold_attach[1])} below 50°F`} />
        <Stat label="Game window lift" value={`+${d.headline.game_lift_pp} pp`} hint="in-game vs outside" />
        <Stat label="Summer vs winter" value={`${(d.season.find((s: any) => s.season === 'summer').attach / d.season.find((s: any) => s.season === 'winter').attach).toFixed(2)}×`} />
        <Stat label="Dessert-led attach" value={pct(ov.by_intent.find((i: any) => i.intent_class === 'direct')?.attach ?? 0)} hint="vs meal-led attachment" />
      </div>

      <Section title="Temperature is the driver"
               subtitle="Measured on the log, not asserted. The 39-week window runs December to September so the cold end of this chart has real orders in it.">
        <Card className="p-4">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={temp} margin={{ left: -20, right: 8 }}>
              <CartesianGrid stroke="#eee" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #eee', fontSize: 12 }}
                       formatter={(v: any, n: any, p: any) => [`${Number(v).toFixed(1)}% of ${num(p.payload.n)} orders`, 'attach']} />
              <Bar isAnimationActive={false} dataKey="attach_pct" radius={[6, 6, 0, 0]}>
                {temp.map((t: any, i: number) => (
                  <Cell key={i} fill={`hsl(${145 - i * 20}, ${55 + i * 4}%, ${58 - i * 3}%)`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <p className="mt-2 text-[11.5px] leading-relaxed text-ink-500">
          The 72–82 °F bucket sits below 60–72 °F rather than between it and the next. These are
          observational buckets, not a controlled sweep: 72–82 °F pools warm spring afternoons with
          cool summer evenings, and the hour and season mixed into each bucket differ. The trend
          across the range is the signal; the single inversion is the confound.
        </p>
      </Section>

      <div className="grid gap-4 lg:grid-cols-3">
        <DriverTable title="Weather" rows={d.weather} k="weather" />
        <DriverTable title="Season" rows={d.season} k="season" />
        <DriverTable title="Intent" rows={d.intent} k="intent_class" />
      </div>

      <Section title="Hour of day" subtitle="Attach by hour across the whole log.">
        <Card className="p-4">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.hour.map((h: any) => ({ ...h, attach_pct: h.attach * 100 }))} margin={{ left: -20, right: 8 }}>
              <CartesianGrid stroke="#eee" vertical={false} />
              <XAxis dataKey="hour" tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#6b6b6b' }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #eee', fontSize: 12 }} />
              <Bar isAnimationActive={false} dataKey="attach_pct" fill="#06c167" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </Section>
    </div>
  )
}

function DriverTable({ title, rows, k }: { title: string; rows: any[]; k: string }) {
  const max = Math.max(...rows.map((r) => r.attach))
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-ink-100 px-4 py-2.5 text-[13px] font-bold">{title}</div>
      <table className="w-full text-[12.5px]">
        <tbody className="divide-y divide-ink-100">
          {rows.map((r) => (
            <tr key={String(r[k])}>
              <td className="px-4 py-2 font-semibold capitalize">{String(r[k])}</td>
              <td className="w-[45%] py-2 pr-3">
                <div className="h-1.5 w-full rounded-full bg-ink-50">
                  <div className="h-1.5 rounded-full bg-brand-500" style={{ width: `${(r.attach / max) * 100}%` }} />
                </div>
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{pct(r.attach)}</td>
              <td className="px-4 py-2 text-right tabular-nums text-ink-500">{num(r.n)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function Validation({ d, meta }: { d: any; meta: any }) {
  return (
    <div className="space-y-6">
      <Card className="flex gap-3 border-cool-500/20 bg-cool-50 p-4">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-cool-500" />
        <p className="text-[12.5px] leading-relaxed text-ink-700">{d.disclosure}</p>
      </Card>

      <Section title="Does the estimate recover the truth?"
               subtitle="The generator knows each arm's real effect. If the number recovered from the randomised log misses it, the analysis layer is wrong — not the data.">
        <Card className="overflow-hidden">
          <table className="w-full text-[12.5px]">
            <thead className="bg-ink-50 text-[10px] font-bold uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-2.5 text-left">Arm</th>
                <th className="px-3 py-2.5 text-right">True uplift</th>
                <th className="px-3 py-2.5 text-right">Recovered</th>
                <th className="px-3 py-2.5 text-right">Error</th>
                <th className="px-4 py-2.5 text-center">Inside 95% CI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {d.arms.filter((a: any) => a.arm !== 'none').map((a: any) => (
                <tr key={a.arm}>
                  <td className="px-4 py-2.5 font-semibold">{a.arm}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">+{a.true_uplift_pp.toFixed(2)}pp</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">+{a.observed_uplift_pp.toFixed(2)}pp</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-ink-500">{a.abs_error_pp.toFixed(2)}pp</td>
                  <td className="px-4 py-2.5 text-center">
                    {a.inside_ci
                      ? <CheckCircle2 className="mx-auto h-4 w-4 text-brand-600" />
                      : <XCircle className="mx-auto h-4 w-4 text-risk-500" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <p className="mt-2 text-[12px] text-ink-500">
          Largest absolute error {d.max_abs_error_pp} pp; every arm lands inside its confidence interval.
        </p>
      </Section>

      <Section title="Generator quality gate" subtitle="Ten checks, run on every regeneration. A failure blocks the dataset.">
        <Card className="divide-y divide-ink-100">
          {d.checks.map((c: any, i: number) => (
            <div key={i} className="flex items-start gap-3 px-4 py-2.5 text-[12.5px]">
              {c.pass
                ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-risk-500" />}
              <div>
                <div className="font-semibold text-ink-900">{c.check}</div>
                {c.detail && <div className="text-ink-500">{c.detail}</div>}
              </div>
            </div>
          ))}
        </Card>
      </Section>
    </div>
  )
}
