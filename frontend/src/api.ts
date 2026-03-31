const base = (import.meta.env.VITE_API_URL || '').replace(/\/api$/, '')

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export type Signal = 'buy' | 'sell' | 'hold'

export interface DashboardRow {
  asset: {
    id: number
    symbol: string
    name: string
    asset_type: string
  }
  last_quote: { ts: string; close: number } | null
  latest_prediction: {
    id: number
    created_at: string
    signal: Signal
    confidence: number
    base_price: number
    predicted_value: number
    target_date: string
    model_version: string
  } | null
}

export interface QuotePoint {
  ts: string
  open: number | null
  high: number | null
  low: number | null
  close: number
  volume: number | null
}

export interface PredictionRow {
  id: number
  asset_id: number
  created_at: string
  horizon_days: number
  target_date: string
  base_price: number
  predicted_value: number
  signal: Signal
  confidence: number
  model_version: string
  features: Record<string, unknown> | null
  outcome: {
    actual_value: number
    evaluated_at: string
    metrics: Record<string, unknown> | null
  } | null
}

export interface NewsRow {
  id: number
  published_at: string
  title: string
  url: string | null
  source: string | null
  snippet: string | null
  sentiment: number | null
}

export function getDashboard() {
  return fetchJson<DashboardRow[]>('/api/dashboard')
}

export function getQuotes(assetId: number) {
  return fetchJson<QuotePoint[]>(`/api/assets/${assetId}/quotes`)
}

export function getPredictions(assetId: number) {
  return fetchJson<PredictionRow[]>(`/api/assets/${assetId}/predictions?limit=100`)
}

export function getNews(assetId: number) {
  return fetchJson<NewsRow[]>(`/api/assets/${assetId}/news`)
}

export function getMetricsSummary(days = 90) {
  return fetchJson<{
    since: string
    by_version: { model_version: string; count: number; mean_abs_pct_error: number }[]
  }>(`/api/metrics/summary?days=${days}`)
}

export function getMetricsByAsset(days = 90) {
  return fetchJson<
    {
      asset_id: number
      symbol: string
      evaluated_predictions: number
      mean_abs_pct_error: number
    }[]
  >(`/api/metrics/by-asset?days=${days}`)
}

export function getModelRecommendation(days = 90) {
  return fetchJson<
    | {
        recommended_version: string
        mean_abs_pct_error: number
        sample_count: number
        all_versions: { model_version: string; count: number; mean_abs_pct_error: number }[]
      }
    | { message: string }
  >(`/api/metrics/model-recommendation?days=${days}`)
}

export function postFullPipeline(forceNews = false) {
  const q = forceNews ? '?force_news=1' : ''
  return fetchJson<Record<string, unknown>>(`/api/jobs/full-pipeline${q}`, { method: 'POST' })
}

export interface WalkForwardRow {
  asset_id: number
  symbol: string | null
  n_steps: number
  train_min: number
  step: number
  ensemble: boolean
  mean_abs_pct_error: number
  median_abs_pct_error: number
  directional_accuracy: number
  signal_match_rate: number
}

export interface WalkForwardAll {
  assets: (WalkForwardRow | Record<string, unknown>)[]
  train_min: number
  step: number
}

export function getWalkForward(opts?: {
  assetId?: number
  trainMin?: number
  step?: number
  ensemble?: boolean
}) {
  const sp = new URLSearchParams()
  if (opts?.assetId != null) sp.set('asset_id', String(opts.assetId))
  if (opts?.trainMin != null) sp.set('train_min', String(opts.trainMin))
  if (opts?.step != null) sp.set('step', String(opts.step))
  if (opts?.ensemble != null) sp.set('ensemble', opts.ensemble ? '1' : '0')
  const q = sp.toString()
  return fetchJson<WalkForwardAll | WalkForwardRow>(`/api/metrics/walk-forward${q ? `?${q}` : ''}`)
}
