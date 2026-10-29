import { useEffect, useState } from 'react'
import { CloudSnow, Sun, Umbrella, Wind, Cloud, Clock, CalendarDays, PartyPopper } from 'lucide-react'
import { post } from '../lib/api'
import { ContextSel } from '../lib/types'
import { Card, ErrorNote } from './ui'

type Row = {
  value: string; label: string; is_current: boolean
  demand_index: number; absolute_index: number; temperature_f: number
  magnum_best_rank: number | null; magnum_in_top5: number
  vs_current_pct: number | null
  top: { sku_id: string; name: string; flavour: string | null; score: number }[]
}

const DIMS = [
  { id: 'weather', label: 'Weather', icon: Cloud },
  { id: 'time_window', label: 'Time of day', icon: Clock },
  { id: 'day', label: 'Day', icon: CalendarDays },
  { id: 'event', label: 'Occasion', icon: PartyPopper },
] as const

const WEATHER_ICON: Record<string, any> = {
  hot: Sun, warm: Sun, cool: Wind, rain: Umbrella, snow: CloudSnow,
}

/**
 * The response surface, not one point on it.
 *
 * A resolved context tells a reviewer what the system does now. It does not
 * show that the system is reacting to anything - for that you have to sweep
 * the axis. Each cell is a real `context.sensitivity` result off the same
 * resolve/rank path the live screen uses, so the preview cannot drift from
 * what clicking it actually produces.
 */
export default function WhatIfStrip({
  sel, setSel, customerId,
}: {
  sel: ContextSel
  setSel: (s: ContextSel) => void
  customerId: string | null
}) {
  const [dim, setDim] = useState<string>('weather')
  const [data, setData] = useState<{ rows: Row[]; latency_ms: number } | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    let live = true
    setError(null)
    post<any>('/api/context/sensitivity', { customer_id: customerId, context: sel, dimension: dim })
      .then((r) => live && setData(r))
      .catch((e) => live && setError(e))
    return () => { live = false }
  }, [dim, customerId, JSON.stringify(sel)])

  const rows = data?.rows ?? []
  const max = Math.max(1, ...rows.map((r) => r.absolute_index))

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-ink-100 px-4 py-3">
        <div className="leading-tight">
          <div className="text-[14px] font-bold tracking-tight">If the world changed right now</div>
          <div className="text-[11.5px] text-ink-500">
            Everything else held fixed. Click a bar to actually apply it.
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1">
          {DIMS.map((d) => {
            const Icon = d.icon
            return (
              <button
                key={d.id}
                onClick={() => setDim(d.id)}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold transition ${
                  dim === d.id ? 'bg-ink-900 text-white' : 'text-ink-500 hover:bg-ink-50'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {d.label}
              </button>
            )
          })}
        </div>
      </div>

      {error ? <div className="p-4"><ErrorNote error={error} /></div> : null}

      <div className="grid gap-2 p-4" style={{ gridTemplateColumns: `repeat(${Math.max(1, rows.length)}, minmax(0,1fr))` }}>
        {rows.map((r) => {
          const Icon = dim === 'weather' ? WEATHER_ICON[r.value] : null
          const h = Math.round((r.absolute_index / max) * 100)
          const up = (r.vs_current_pct ?? 0) > 0
          return (
            <button
              key={r.value}
              onClick={() => setSel({ ...sel, [dim]: r.value } as ContextSel)}
              title={`${r.label}: demand index ${r.demand_index}, top pick ${r.top[0]?.name ?? '—'}`}
              className={`group flex flex-col items-center gap-1.5 rounded-xl border px-2 pb-2 pt-3 transition ${
                r.is_current
                  ? 'border-brand-500 bg-brand-50'
                  : 'border-ink-100 bg-white hover:border-ink-300 hover:bg-ink-50'
              }`}
            >
              <div className="flex h-20 w-full items-end justify-center">
                <div
                  className={`w-8 rounded-t-md transition-all ${
                    r.is_current ? 'bg-brand-500' : up ? 'bg-warn-500/70' : 'bg-cool-500/50'
                  }`}
                  style={{ height: `${Math.max(6, h)}%` }}
                />
              </div>
              <div className="flex items-center gap-1 text-[11.5px] font-bold text-ink-900">
                {Icon && <Icon className="h-3 w-3" />}
                <span className="truncate">{r.label}</span>
              </div>
              <div className="text-[11px] font-semibold tabular-nums text-ink-500">
                {r.absolute_index.toFixed(2)}×
              </div>
              <div
                className={`text-[10.5px] font-bold tabular-nums ${
                  r.is_current ? 'text-brand-700' : up ? 'text-warn-500' : 'text-cool-500'
                }`}
              >
                {r.is_current ? 'now' : `${up ? '+' : ''}${r.vs_current_pct?.toFixed(0)}%`}
              </div>
              {dim === 'weather' && (
                <div className="text-[10px] tabular-nums text-ink-500">{Math.round(r.temperature_f)}°F</div>
              )}
            </button>
          )
        })}
      </div>

      <div className="border-t border-ink-100 bg-ink-50/60 px-4 py-2 text-[11px] text-ink-500">
        Bars are the absolute demand index — demand against a fixed reference,
        not against the same hour, so the clock and the calendar are allowed to
        matter. Computed in {data?.latency_ms ?? 0} ms.
      </div>
    </Card>
  )
}
