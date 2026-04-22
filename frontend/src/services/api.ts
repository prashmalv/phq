import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

export const api = axios.create({ baseURL: BASE_URL })

// ─── Types ───────────────────────────────────────────────────────────────────

export interface QueryResponse {
  answer: string
  confidence: number
  sources: string[]
  evidence_count: number
  latency_ms: number
  parsed_intent: Record<string, unknown>
  cached: boolean
}

export interface Event {
  event_id: string
  content: string
  source: string
  event_type: string
  sentiment: number
  district: string
  city?: string
  occurred_at: string
  credibility: number
  tags: string[]
}

export interface DistrictSummary {
  district: string
  count: number
  avg_sentiment: number
}

export interface TrendPoint {
  day: string
  count: number
  avg_sentiment: number
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export const sendQuery = async (query: string): Promise<QueryResponse> => {
  const { data } = await api.post<QueryResponse>('/chat/query', { query })
  return data
}

// ─── Events ──────────────────────────────────────────────────────────────────

export const getRecentEvents = async (params?: {
  district?: string
  event_type?: string
  days?: number
  limit?: number
}): Promise<Event[]> => {
  const { data } = await api.get<Event[]>('/events/recent', { params })
  return data
}

export const getDistrictSummary = async (days = 30): Promise<DistrictSummary[]> => {
  const { data } = await api.get<DistrictSummary[]>('/events/district-summary', {
    params: { days },
  })
  return data
}

export const getDistrictTrend = async (district: string, days = 30): Promise<TrendPoint[]> => {
  const { data } = await api.get<TrendPoint[]>('/analytics/trend', {
    params: { district, days },
  })
  return data
}
