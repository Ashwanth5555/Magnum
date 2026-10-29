export type Ctx = {
  context_id: string; area_id: string; store_id: string; day: string; day_of_week: number
  is_weekend: boolean; time_window: string; time_window_label: string; hour: number
  season: string; weather: string; game_day: boolean; in_game_window: boolean
  event: string; activity: string; temperature_f: number; humidity_pct: number
  temp_anomaly_f: number; demand_index: number; absolute_index: number
  group_bias: number; heat_pull: number; activity_index: number
}
export type ContextSel = {
  day: string; time_window: string; season: string; weather: string
  game_day: boolean; event: string; activity: string; area_id: string
}
export type Reason = { code: string; label: string; customer: string; family: string }
export type Contribution = { family: string; label?: string; weight: number; score: number; points: number }
export type Product = {
  sku_id: string; name: string; brand: string; category: string; subcategory: string
  flavour?: string | null; size_label: string; units_in_pack: number; price: number
  unit_margin: number; is_shareable: boolean
}
export type Ranked = Product & {
  match_score: number; stock_state: string; on_hand: number
  reason_codes: string[]; reasons: Reason[]; contributions: Contribution[]
}
export type CartLine = { sku_id: string; quantity: number }
export type Candidate = {
  arm: string; offer_id: string; label: string; target_sku: string | null
  discount_pct: number; base_discount_pct?: number; depth_reason?: string | null
  discount_value: number; contact_cost: number
  predicted_uplift_pp: number; expected_incremental_margin: number
  eligible: boolean; failed_rule: string | null; reasons: Reason[]
}
export type Decision = {
  action: string; offer: Candidate | null; suppression_reason: string | null
  candidates: Candidate[]; reasons: Reason[]; guardrails: Record<string, any>
  policy_version: string; latency_ms: number
}
export type Hour = {
  offset: number; hour: number; day: string; p10: number; p50: number; p90: number
  demand_index: number; absolute_index: number; temperature_f: number; in_game_window: boolean
}
export type StockAction = {
  sku_id: string; name: string; status: string; on_hand: number; inbound: number
  safety_stock: number; forecast_p50_to_peak: number; forecast_p90_to_peak: number
  gap: number; action: string; action_units: number; peak: any
  needed_by_offset_hours: number; transfer_lead_minutes: number; reasons: Reason[]
}
