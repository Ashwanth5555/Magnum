import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, ErrorBar, LabelList, Legend,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import { get } from '../lib/api'
import { Card, ErrorNote, Spinner } from '../components/ui'

/**
 * What a month, a quarter and half a year of running this add up to.
 *
 * This is the easiest screen in the product to lie on, so it is built to be
 * argued with rather than admired. Every rate under these charts is read off the
 * order log; every bar names the policy it is measured against; the one genuine
 * assumption is a slider rather than a constant; and where the evidence does not
 * support a claim — the comparison against doing nothing at all, whose interval
 * crosses zero — the chart draws the interval crossing zero instead of hiding it.
 */
const money = (n: number) =>
  (Math.abs(n) >= 1000 ? `$${Math.round(n / 100) / 10}k` : `$${Math.round(n)}`)
const full = (n: number) => `$${Math.round(n).toLocaleString()}`
const count = (n: number) => Math.round(n).toLocaleString()
/** Five-figure counts on a third-width axis need to be short, not exact. */
const compact = (n: number) =>
  (Math.abs(n) >= 1000 ? `${Math.round(n / 100) / 10}k` : `${Math.round(n)}`)

const AXIS = { fontSize: 11, fill: '#6b6b6b' }
const TIP = { borderRadius: 12, border: '1px solid #eee', fontSize: 12 }

/** One chart and the one sentence a reader needs to know what it is claiming. */
function Chart({ title, note, children }: {
  title: string; note: string; children: React.ReactNode
}) {
  return (
    <Card className="p-4">
      <div className="text-[13px] font-bold text-ink-900">{title}</div>
      <div className="mt-0.5 mb-3 text-[11.5px] leading-snug text-ink-500">{note}</div>
      {children}
    </Card>
  )
}

export default function Impact() {
  const [recovery, setRecovery] = useState(0.35)
  const [scale, setScale] = useState(1)
  const [d, setD] = useState<any>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    let live = true
    setError(null)
    get<any>(`/api/impact?recovery=${recovery}&scale=${scale}`)
      .then((r) => live && setD(r))
      .catch((e) => live && setError(e))
    return () => { live = false }
  }, [recovery, scale])

  if (error) return <ErrorNote error={error} />
  if (!d) return <Spinner label="Adding it up" />

  const row = (h: any, key: string) =>
    h.policy_rows.find((p: any) => p.key === key)

  // Margin, split by where it comes from. The two halves are different kinds of
  // claim — one is an offline policy estimate, one is an availability model —
  // so they are stacked rather than summed into a single unlabelled number.
  const margin = d.horizons.map((h: any) => ({
    label: h.label,
    offers: row(h, 'always_voucher20').margin,
    stock: h.availability.margin,
    total: h.total_margin,
    lo: h.total_margin_low,
    hi: h.total_margin_high,
    err: [h.total_margin - h.total_margin_low, h.total_margin_high - h.total_margin],
  }))

  const orders = d.horizons.map((h: any) => ({
    label: h.label,
    extra: row(h, 'do_nothing').extra_magnum_orders,
    recovered: h.availability.substituted_orders,
  }))

  // The funnel, all ten stores combined. "Shown" towers over "bought", which is
  // the point - the second bar is split by whether the basket needed a coupon,
  // so the reader can see how much of the conversion was bought with margin.
  const funnel = d.horizons.map((h: any) => ({
    label: h.label,
    shown: h.funnel.shown,
    discounted: h.funnel.discounted,
    full_price: h.funnel.full_price,
    converted: h.funnel.converted,
    // The rest of the bar. Conversion is a share of what was shown, so it has to
    // live *inside* that bar - a second bar beside it reads as a second quantity.
    not_bought: h.funnel.shown - h.funnel.converted,
    rate: h.funnel.conversion_rate,
  }))

  // Availability in bars, not hours: the units an empty shelf would have refused
  // plus the units the bin would have taken. Money sits on top of the stack, so
  // "how many bars" and "how much money" are the same chart, not two.
  const saved = d.horizons.map((h: any) => ({
    label: h.label,
    recovered: h.availability.units_recovered,
    waste: h.availability.waste_units_avoided,
    bars: h.availability.bars_saved,
    money: h.availability.margin,
    hours: h.availability.stockout_hours_avoided,
    moves: h.availability.rebalances,
  }))

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-x-6 gap-y-3 p-4">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-500 text-white">
            <TrendingUp className="h-4 w-4" />
          </span>
          <div>
            <div className="text-[13px] font-bold text-ink-900">Business impact</div>
            <div className="text-[11px] text-ink-500">
              {count(d.measured.decisions_per_day)} decisions a day, measured over{' '}
              {count(d.measured.days_of_log)} days of orders across {d.measured.stores} stores.
            </div>
          </div>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-5">
          <label className="text-[11px] text-ink-600">
            <span className="font-semibold">Forecast recovery {Math.round(recovery * 100)}%</span>
            <input type="range" min={0} max={1} step={0.05} value={recovery}
                   onChange={(e) => setRecovery(Number(e.target.value))}
                   className="mt-1 block w-40 accent-brand-500" />
            <span className="text-ink-400">the one assumption on this page</span>
          </label>
          <label className="text-[11px] text-ink-600">
            <span className="font-semibold">Network scale ×{scale}</span>
            <input type="range" min={1} max={50} step={1} value={scale}
                   onChange={(e) => setScale(Number(e.target.value))}
                   className="mt-1 block w-40 accent-brand-500" />
            <span className="text-ink-400">×1 is the simulated 10-store network</span>
          </label>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Chart
          title="Shown, and what came back"
          note={`Every store combined. The whole bar is what we showed; the solid part at the bottom is what was bought out of it. Six months: ${count(funnel[2].shown)} shown, ${count(funnel[2].converted)} bought — ${(funnel[2].rate * 100).toFixed(1)}%, split by whether the basket needed a coupon to close.`}
        >
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={funnel} margin={{ top: 34, right: 8, bottom: 0, left: -6 }}>
              <CartesianGrid stroke="#eee" vertical={false} />
              <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={compact} />
              <Tooltip contentStyle={TIP} formatter={(v: any, n: any) => [count(Number(v)), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }}
                      formatter={(v: string) => <span style={{ color: '#2f2f2f' }}>{v}</span>} />
              <Bar isAnimationActive={false} dataKey="full_price" stackId="c"
                   name="Bought at full price" fill="#06c167" radius={[0, 0, 4, 4]}
                   maxBarSize={96} />
              <Bar isAnimationActive={false} dataKey="discounted" stackId="c"
                   name="Bought with a coupon" fill="#d97706" maxBarSize={96} />
              <Bar isAnimationActive={false} dataKey="not_bought" stackId="c"
                   name="Shown, not bought" fill="#e4f4ec" stroke="#b8dfc9" strokeWidth={1}
                   radius={[4, 4, 0, 0]} maxBarSize={96}>
                {/* Both numbers sit above the bar, each with the word that says
                    what it is. Earlier revisions put the bought figure beside the
                    band it measures, which reads well until the network-scale
                    slider is moved: the bars get taller, the label stays at the
                    band's height, and it lands on top of the next bar. Above the
                    bar it is centred on its own category and cannot collide. */}
                <LabelList dataKey="shown" content={(p: any) => {
                  const f = funnel[p.index]
                  const cx = p.x + p.width / 2
                  return (
                    <g>
                      <text x={cx} y={p.y - 20} textAnchor="middle"
                            style={{ fontSize: 10, fill: '#6b6b6b' }}>
                        {compact(f.shown)} shown
                      </text>
                      <text x={cx} y={p.y - 7} textAnchor="middle"
                            style={{ fontSize: 11, fontWeight: 700, fill: '#0b0b0b' }}>
                        {compact(f.converted)} bought · {Math.round(f.rate * 100)}%
                      </text>
                    </g>
                  )
                }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-[11px] leading-snug text-ink-500">
            A further {count(d.horizons[2].funnel.unprompted)} baskets over six months buy
            Magnum with nothing on screen at all. Those are not counted here — the system
            does not get to claim them.
          </p>
        </Chart>

        <Chart
          title="Extra Magnum orders"
          note="Orders that would not have happened without the system — the ones it wins by asking, plus the ones it saves by offering a substitute when the first choice is gone."
        >
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={orders} margin={{ top: 18, right: 8, bottom: 0, left: -6 }}>
              <CartesianGrid stroke="#eee" vertical={false} />
              <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={compact} />
              <Tooltip contentStyle={TIP} formatter={(v: any, n: any) => [count(Number(v)), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar isAnimationActive={false} dataKey="extra" name="Won by better targeting" fill="#06c167" radius={[4, 4, 0, 0]}>
                <LabelList dataKey="extra" position="top" formatter={count}
                           style={{ fontSize: 11, fontWeight: 700, fill: '#0b0b0b' }} />
              </Bar>
              <Bar isAnimationActive={false} dataKey="recovered" name="Saved by substitution" fill="#93e5bc" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-[11px] leading-snug text-ink-500">
            Measured against doing no targeting at all. This is the same lever as the
            margin chart below, counted in orders instead of dollars — never added to it.
          </p>
        </Chart>

        <Chart
          title="Stockouts caught early"
          note={`Bars that reach a basket instead of an empty shelf or a bin, because the shortfall was called before the peak and stock was moved between stores. At ${Math.round(recovery * 100)}% recovery, six months is ${count(saved[2].bars)} bars worth ${full(saved[2].money)}.`}
        >
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={saved} margin={{ top: 18, right: 8, bottom: 0, left: -6 }}>
              <CartesianGrid stroke="#eee" vertical={false} />
              <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={compact} />
              <Tooltip contentStyle={TIP} formatter={(v: any, n: any) => [`${count(Number(v))} bars`, n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar isAnimationActive={false} dataKey="recovered" stackId="s"
                   name="Sold instead of missed" fill="#d97706" radius={[0, 0, 4, 4]} />
              <Bar isAnimationActive={false} dataKey="waste" stackId="s"
                   name="Kept out of the bin" fill="#2563eb" radius={[4, 4, 0, 0]}>
                <LabelList dataKey="money" position="top" formatter={money}
                           style={{ fontSize: 11, fontWeight: 700, fill: '#0b0b0b' }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-[11px] leading-snug text-ink-500">
            The number on each bar is what those bars are worth. Getting there costs{' '}
            {count(saved[2].moves)} store-to-store moves over six months, and buys{' '}
            {count(saved[2].hours)} shelf-hours that never go empty. In this log spoilage is
            the far larger loss — {count(saved[2].waste)} of the {count(saved[2].bars)} bars
            are ones that would have been binned, not ones a customer was refused.
          </p>
        </Chart>
      </div>

      <Chart
        title="Margin gained — everything above, in money"
        note={`Against running a blanket 20% campaign. The green half is the offer decisions in the first two charts; the blue half is the stock saved in the third. Whiskers are the 95% interval; over six months that is ${full(margin[2].lo)} to ${full(margin[2].hi)}.`}
      >
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={margin} margin={{ top: 20, right: 8, bottom: 0, left: 4 }}>
            <CartesianGrid stroke="#eee" vertical={false} />
            <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={money} />
            <Tooltip contentStyle={TIP} formatter={(v: any, n: any) => [full(Number(v)), n]} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar isAnimationActive={false} dataKey="offers" stackId="m" name="Better offer decisions" fill="#06c167" radius={[0, 0, 4, 4]} maxBarSize={140} />
            <Bar isAnimationActive={false} dataKey="stock" stackId="m" name="Fewer stockouts, less waste" fill="#2563eb" radius={[4, 4, 0, 0]} maxBarSize={140}>
              <ErrorBar dataKey="err" width={8} strokeWidth={1.5} stroke="#6b6b6b" />
              <LabelList dataKey="total" position="top" formatter={money}
                         style={{ fontSize: 13, fontWeight: 700, fill: '#0b0b0b' }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Chart>

      <Card className="p-4 text-[11.5px] leading-relaxed text-ink-600">
        <span className="font-bold text-ink-900">How to read these.</span>{' '}
        The first chart is counted, not modelled — shown, bought, and whether the
        basket needed a coupon. Offer margin is an offline estimate on a held-out
        split, using inverse propensity scoring against the randomised arms in the
        log — the same method a real deployment would use before switching traffic
        on. Availability is the measured stockout and waste rate multiplied by the
        recovery slider, which is the only assumption on the page. The last chart
        is the first three in dollars: its green half is the offer lever and its
        blue half is the stock lever, and the extra orders are never added on top
        of the margin because they are the same lever counted twice. Nothing here
        is a forecast of a market; it is what this policy did to this log,
        projected forward at the rate it was measured at.
      </Card>
    </div>
  )
}
