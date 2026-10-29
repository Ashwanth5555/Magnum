import { Component, ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-ink-100 bg-white ${className}`}>{children}</div>
  )
}

export function Section({
  title, subtitle, right, children, className = '',
}: { title: string; subtitle?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <div className="mb-3 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-[19px] font-bold tracking-tight text-ink-900">{title}</h2>
          {subtitle && <p className="mt-0.5 max-w-2xl text-[13px] leading-snug text-ink-500">{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  )
}

export function Badge({
  children, tone = 'neutral', className = '',
}: { children: ReactNode; tone?: 'neutral' | 'brand' | 'warn' | 'risk' | 'cool'; className?: string }) {
  const tones = {
    neutral: 'bg-ink-50 text-ink-700 ring-ink-100',
    brand: 'bg-brand-50 text-brand-700 ring-brand-500/20',
    warn: 'bg-warn-50 text-warn-500 ring-warn-500/20',
    risk: 'bg-risk-50 text-risk-500 ring-risk-500/20',
    cool: 'bg-cool-50 text-cool-500 ring-cool-500/20',
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${tones[tone]} ${className}`}>
      {children}
    </span>
  )
}

export function Stat({
  label, value, hint, tone = 'neutral',
}: { label: string; value: ReactNode; hint?: ReactNode; tone?: 'neutral' | 'brand' | 'risk' }) {
  const fg = tone === 'brand' ? 'text-brand-600' : tone === 'risk' ? 'text-risk-500' : 'text-ink-900'
  return (
    <div className="rounded-2xl border border-ink-100 bg-white px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold tabular-nums tracking-tight ${fg}`}>{value}</div>
      {hint && <div className="mt-0.5 text-[12px] leading-snug text-ink-500">{hint}</div>}
    </div>
  )
}

export function Toggle({
  on, onChange, label,
}: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      onClick={() => onChange(!on)}
      aria-pressed={on}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[13px] font-semibold transition ${
        on ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-ink-100 bg-white text-ink-500 hover:border-ink-300'
      }`}
    >
      <span className={`h-3.5 w-3.5 rounded-full ring-2 ring-inset transition ${on ? 'bg-brand-500 ring-brand-500' : 'bg-white ring-ink-300'}`} />
      {label}
    </button>
  )
}

export function Select({
  value, onChange, options, label,
}: {
  value: string; onChange: (v: string) => void; label: string
  options: { value: string; label: string }[]
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-wider text-ink-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-xl border border-ink-100 bg-white px-2.5 text-[13px] font-semibold text-ink-900 outline-none transition focus:border-brand-500 hover:border-ink-300"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-[13px] text-ink-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-100 border-t-brand-500" />
      {label}…
    </div>
  )
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <div className="rounded-2xl border border-risk-500/20 bg-risk-50 px-4 py-3 text-[13px] text-risk-500">
      {String((error as Error)?.message ?? error)}
    </div>
  )
}

/** A weighted-contribution bar. Used everywhere a score is shown, because a
 *  number the reviewer cannot decompose is not evidence of anything. */
export function ContribBar({ items }: { items: { family: string; label?: string; points: number }[] }) {
  const total = items.reduce((a, b) => a + Math.max(0, b.points), 0) || 1
  const colors: Record<string, string> = {
    text: 'bg-ink-300', personal: 'bg-brand-500', peer: 'bg-brand-200',
    context: 'bg-warn-500', availability: 'bg-cool-500', pairing: 'bg-violet-500',
  }
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-ink-50">
      {items.map((i) => (
        <div
          key={i.family}
          title={`${i.label ?? i.family}: ${i.points.toFixed(3)}`}
          className={colors[i.family] ?? 'bg-ink-300'}
          style={{ width: `${(Math.max(0, i.points) / total) * 100}%` }}
        />
      ))}
    </div>
  )
}

/**
 * A screen-level boundary.
 *
 * React unmounts the entire tree when a render throws, which turns one bad
 * field into a white page. That is survivable in development and not survivable
 * in front of a client, so every screen renders inside one of these: the
 * failure stays inside the panel that caused it and the rest of the console
 * keeps working.
 */
export class ScreenBoundary extends Component<
  { children: ReactNode; name: string },
  { error: Error | null }
> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error) {
    console.error('[ScreenBoundary]', this.props.name, error)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="rounded-2xl border border-risk-500/20 bg-risk-50 px-5 py-4">
        <div className="text-[14px] font-bold text-risk-500">
          The {this.props.name} screen hit an error and stopped rendering.
        </div>
        <p className="mt-1 text-[12.5px] leading-snug text-ink-700">
          The rest of the console is unaffected — switch tabs and come back, or
          reset the demo. The details are below and in the browser console.
        </p>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-white/70 p-3 text-[11.5px] text-ink-700">
          {String(this.state.error?.message ?? this.state.error)}
        </pre>
        <button
          onClick={() => this.setState({ error: null })}
          className="mt-3 rounded-full bg-ink-900 px-4 py-2 text-[12px] font-bold text-white transition hover:bg-brand-500"
        >
          Try again
        </button>
      </div>
    )
  }
}
