import { useEffect, useState } from 'react'
import { Lock, Table2, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { get, qs } from '../lib/api'
import { num } from '../lib/format'
import { Badge, Card, ErrorNote, Section, Spinner } from '../components/ui'

export default function DataExplorer({ meta }: { meta: any }) {
  const [tables, setTables] = useState<any[]>([])
  const [active, setActive] = useState('orders')
  const [page, setPage] = useState(0)
  const [order, setOrder] = useState<{ by: string | null; dir: 'asc' | 'desc' }>({ by: null, dir: 'asc' })
  const [filter, setFilter] = useState({ column: '', q: '' })
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState<unknown>(null)
  const LIMIT = 25

  useEffect(() => { get<any>('/api/data/tables').then((r) => setTables(r.tables)).catch(setError) }, [])

  useEffect(() => {
    setData(null)
    get<any>(`/api/data/table/${active}?${qs({
      limit: LIMIT, offset: page * LIMIT, order_by: order.by, direction: order.dir,
      column: filter.column, q: filter.q,
    })}`).then(setData).catch(setError)
  }, [active, page, order, filter])

  const locked = tables.filter((t) => t.locked)
  const open = tables.filter((t) => !t.locked)

  return (
    <div className="space-y-6">
      <Section title="Data explorer"
               subtitle="Every table the application reads, straight from the SQLite file the generator wrote. The two evaluation tables are listed and refused.">
        <div className="flex flex-wrap gap-2">
          {open.map((t) => (
            <button key={t.table}
              onClick={() => { setActive(t.table); setPage(0); setOrder({ by: null, dir: 'asc' }); setFilter({ column: '', q: '' }) }}
              className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-[12.5px] font-semibold transition ${
                active === t.table ? 'border-ink-900 bg-ink-900 text-white' : 'border-ink-100 text-ink-700 hover:border-ink-300'}`}>
              <Table2 className="h-3.5 w-3.5" />
              {t.table}
              <span className={active === t.table ? 'text-white/60' : 'text-ink-500'}>{num(t.rows)}</span>
            </button>
          ))}
          {locked.map((t) => (
            <div key={t.table} title={t.reason}
                 className="flex cursor-not-allowed items-center gap-2 rounded-xl border border-dashed border-ink-300 px-3 py-2 text-[12.5px] font-semibold text-ink-300">
              <Lock className="h-3.5 w-3.5" />
              {t.table}
              <span>{num(t.rows)}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[12px] leading-relaxed text-ink-500">
          <Lock className="mr-1 inline h-3 w-3" />
          <strong className="text-ink-700">{meta.held_out_tables.join(' and ')}</strong> hold the propensities and traits
          the generator used. They are evaluation-only: the explorer returns <code>403</code> for them, and the single
          read anywhere in the service is the validation panel, which returns five summary rows and no per-decision score.
        </p>
      </Section>

      {error && <ErrorNote error={error} />}
      {!data && !error && <Spinner />}

      {data && (
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 px-4 py-3">
            <span className="text-[13px] font-bold">{data.table}</span>
            <Badge tone="neutral">{num(data.total)} rows</Badge>
            <div className="ml-auto flex items-center gap-2">
              <select value={filter.column} onChange={(e) => { setFilter({ ...filter, column: e.target.value }); setPage(0) }}
                      className="h-8 rounded-lg border border-ink-100 px-2 text-[12px] font-semibold outline-none hover:border-ink-300">
                <option value="">Filter column…</option>
                {data.columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
              </select>
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-500" />
                <input value={filter.q} disabled={!filter.column}
                       onChange={(e) => { setFilter({ ...filter, q: e.target.value }); setPage(0) }}
                       placeholder="contains…"
                       className="h-8 w-40 rounded-lg border border-ink-100 pl-8 pr-2 text-[12px] outline-none focus:border-brand-500 disabled:bg-ink-50" />
              </div>
              <div className="flex items-center gap-1">
                <button disabled={page === 0} onClick={() => setPage(page - 1)}
                        className="grid h-8 w-8 place-items-center rounded-lg border border-ink-100 disabled:opacity-30 hover:border-ink-300">
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="w-24 text-center text-[12px] tabular-nums text-ink-500">
                  {num(page * 25 + 1)}–{num(Math.min((page + 1) * 25, data.total))}
                </span>
                <button disabled={(page + 1) * 25 >= data.total} onClick={() => setPage(page + 1)}
                        className="grid h-8 w-8 place-items-center rounded-lg border border-ink-100 disabled:opacity-30 hover:border-ink-300">
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead className="bg-ink-50 text-[10px] font-bold uppercase tracking-wider text-ink-500">
                <tr>
                  {data.columns.map((c: string) => (
                    <th key={c}
                        onClick={() => setOrder({ by: c, dir: order.by === c && order.dir === 'asc' ? 'desc' : 'asc' })}
                        className="cursor-pointer whitespace-nowrap px-3 py-2 text-left hover:text-ink-900">
                      {c}{order.by === c ? (order.dir === 'asc' ? ' ▲' : ' ▼') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {data.rows.map((r: any, i: number) => (
                  <tr key={i} className="hover:bg-ink-50/60">
                    {data.columns.map((c: string) => (
                      <td key={c} className="whitespace-nowrap px-3 py-1.5 tabular-nums text-ink-700">
                        {r[c] === null ? <span className="text-ink-300">null</span>
                          : typeof r[c] === 'number' ? Number(r[c].toFixed?.(4) ?? r[c]) : String(r[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
