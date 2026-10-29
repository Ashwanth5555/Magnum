import { useEffect, useState } from 'react'
import { CloudSnow, CloudRain, Sun, Thermometer, Trophy, MapPin, User, Users, RotateCcw, ChevronDown } from 'lucide-react'
import { Ctx, ContextSel } from '../lib/types'
import { deg } from '../lib/format'
import { Badge } from './ui'

const WEATHER_ICON: Record<string, any> = { hot: Sun, warm: Sun, cool: Thermometer, rain: CloudRain, snow: CloudSnow }

/** The one control every screen reads. Search, cart, offers, reorder and the
 *  demand desk all resolve against this snapshot, which is what stops the
 *  console from becoming five unrelated dashboards. */
export default function ScenarioBar({
  sel, setSel, ctx, options, onReset, profiles, customerId, setCustomerId,
}: {
  sel: ContextSel
  setSel: (s: ContextSel) => void
  ctx: Ctx | null
  options: any
  onReset: () => void
  profiles: any[]
  customerId: string | null
  setCustomerId: (id: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const Icon = ctx ? WEATHER_ICON[ctx.weather] ?? Sun : Sun

  const plausible: string[] = options?.plausible_weather?.[sel.season] ?? ['hot', 'warm', 'cool', 'rain']
  useEffect(() => {
    if (!plausible.includes(sel.weather)) setSel({ ...sel, weather: plausible[0] })
  }, [sel.season])

  const set = (k: keyof ContextSel, v: any) => setSel({ ...sel, [k]: v })
  const area = options?.areas?.find((a: any) => a.area_id === sel.area_id)

  const lift = ctx ? ctx.demand_index : 1
  const liftTone = lift >= 1.25 ? 'brand' : lift <= 0.85 ? 'cool' : 'neutral'

  return (
    <div className="sticky top-0 z-40 border-b border-ink-100 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-3 gap-y-2 px-5 py-2.5">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 rounded-full border border-ink-100 py-1.5 pl-2.5 pr-2 text-[13px] font-semibold text-ink-900 transition hover:border-ink-300"
        >
          <MapPin className="h-4 w-4 text-brand-600" />
          {area?.name ?? sel.area_id}
          <span className="text-ink-300">·</span>
          <span className="text-ink-500">{area?.state}</span>
          <ChevronDown className={`h-4 w-4 text-ink-500 transition ${open ? 'rotate-180' : ''}`} />
        </button>

        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink-700">
          <Icon className="h-4 w-4 text-warn-500" />
          {ctx ? deg(ctx.temperature_f) : '—'}
          <span className="text-ink-300">·</span>
          <span className="capitalize text-ink-500">{sel.weather}</span>
        </div>

        <div className="text-[13px] font-semibold capitalize text-ink-700">
          {sel.day} <span className="text-ink-500">{ctx?.time_window_label ?? sel.time_window}</span>
        </div>

        {/* Who is shopping is part of the scenario, not part of the chrome. It
            sits with the weather and the hour because every screen resolves
            against the same snapshot, and switching household changes the
            answer exactly the way switching the weather does. */}
        <label className="flex items-center gap-1.5 text-[13px] font-semibold text-ink-700">
          <User className="h-4 w-4 text-ink-500" />
          <select
            value={customerId ?? ''}
            onChange={(e) => setCustomerId(e.target.value || null)}
            className="max-w-[210px] cursor-pointer rounded-full border border-ink-100 bg-white py-1 pl-2 pr-1.5 text-[13px] font-semibold text-ink-900 outline-none transition hover:border-ink-300 focus:border-brand-500"
          >
            <option value="">Guest — no history</option>
            {profiles.map((p) => (
              <option key={p.customer_id} value={p.customer_id}>
                {p.display_name} · {p.cluster.short}
              </option>
            ))}
          </select>
        </label>

        {ctx?.in_game_window && (
          <Badge tone="brand"><Trophy className="h-3 w-3" /> Game window</Badge>
        )}
        {ctx && ctx.event !== 'none' && (
          <Badge tone="cool"><Users className="h-3 w-3" /> {ctx.event.replace('_', ' ')}</Badge>
        )}

        <div className="ml-auto flex items-center gap-2">
          <Badge tone={liftTone as any}>
            demand ×{lift.toFixed(2)} vs a normal {sel.day}
          </Badge>
          <button
            onClick={onReset}
            title="Restore the golden scenario"
            className="rounded-full border border-ink-100 p-1.5 text-ink-500 transition hover:border-ink-300 hover:text-ink-900"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {open && (
        <div className="rise border-t border-ink-100 bg-ink-50/60">
          <div className="mx-auto grid max-w-[1500px] grid-cols-2 gap-3 px-5 py-4 sm:grid-cols-4 lg:grid-cols-8">
            <Field label="Neighborhood">
              <select value={sel.area_id} onChange={(e) => set('area_id', e.target.value)} className={INPUT}>
                {options?.areas?.map((a: any) => (
                  <option key={a.area_id} value={a.area_id}>{a.name} — {a.state}</option>
                ))}
              </select>
            </Field>
            <Field label="Day">
              <select value={sel.day} onChange={(e) => set('day', e.target.value)} className={INPUT}>
                {options?.days?.map((d: string) => (
                  <option key={d} value={d} className="capitalize">{d}</option>
                ))}
              </select>
            </Field>
            <Field label="Time">
              <select value={sel.time_window} onChange={(e) => set('time_window', e.target.value)} className={INPUT}>
                {options?.time_windows?.map((w: any) => (
                  <option key={w.id} value={w.id}>{w.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Season">
              <select value={sel.season} onChange={(e) => set('season', e.target.value)} className={INPUT}>
                {options?.seasons?.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Weather">
              <select value={sel.weather} onChange={(e) => set('weather', e.target.value)} className={INPUT}>
                {plausible.map((w) => (
                  <option key={w} value={w} className="capitalize">{w}</option>
                ))}
              </select>
            </Field>
            <Field label="Event">
              <select value={sel.event} onChange={(e) => set('event', e.target.value)} className={INPUT}>
                {options?.events?.map((e2: any) => (
                  <option key={e2.id} value={e2.id}>{e2.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Activity">
              <select value={sel.activity} onChange={(e) => set('activity', e.target.value)} className={INPUT}>
                {options?.activity?.map((a: any) => (
                  <option key={a.id} value={a.id}>{a.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Game day">
              <button
                onClick={() => set('game_day', !sel.game_day)}
                className={`${INPUT} text-left font-semibold ${sel.game_day ? 'border-brand-500 bg-brand-50 text-brand-700' : ''}`}
              >
                {sel.game_day ? 'Scheduled' : 'No game'}
              </button>
            </Field>
          </div>
          {ctx && (
            <div className="mx-auto max-w-[1500px] px-5 pb-4 text-[12px] leading-relaxed text-ink-500">
              Snapshot <code className="rounded bg-white px-1 py-0.5 text-[11px] text-ink-700">{ctx.context_id}</code> ·{' '}
              {deg(ctx.temperature_f)} ({ctx.temp_anomaly_f >= 0 ? '+' : ''}{ctx.temp_anomaly_f}°F vs the {ctx.season} norm) ·
              heat pull {ctx.heat_pull.toFixed(2)} · group bias {ctx.group_bias.toFixed(2)} ·
              demand ×{ctx.demand_index.toFixed(2)} against the same hour in ordinary conditions.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const INPUT =
  'h-9 w-full rounded-xl border border-ink-100 bg-white px-2.5 text-[13px] font-semibold capitalize text-ink-900 outline-none transition focus:border-brand-500 hover:border-ink-300'

function Field({ label, children }: { label: string; children: any }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-wider text-ink-500">{label}</span>
      {children}
    </label>
  )
}
