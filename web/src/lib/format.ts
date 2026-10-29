export const usd = (n: number, dp = 2) =>
  (n < 0 ? '-$' : '$') + Math.abs(n).toFixed(dp)
export const pct = (n: number, dp = 1) => `${(n * 100).toFixed(dp)}%`
export const pp = (n: number, dp = 2) => `${n >= 0 ? '+' : ''}${n.toFixed(dp)} pp`
export const num = (n: number) => n.toLocaleString('en-US')
export const deg = (n: number) => `${Math.round(n)}°F`

export const tileClass = (p: { category: string; flavour?: string | null }) => {
  if (p.category === 'magnum') return `tile-${p.flavour ?? 'classic'}`
  return `tile-${p.category}`
}
export const hourLabel = (h: number) =>
  h === 0 ? '12a' : h < 12 ? `${h}a` : h === 12 ? '12p' : `${h - 12}p`

export const statusTone = (s: string) =>
  s === 'stockout_risk'
    ? { bg: 'bg-risk-50', fg: 'text-risk-500', ring: 'ring-risk-500/25', label: 'Stockout risk' }
    : s === 'watch'
    ? { bg: 'bg-warn-50', fg: 'text-warn-500', ring: 'ring-warn-500/25', label: 'Watch' }
    : { bg: 'bg-brand-50', fg: 'text-brand-700', ring: 'ring-brand-500/25', label: 'Healthy' }
