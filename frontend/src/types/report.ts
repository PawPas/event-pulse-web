export interface Report {
  id: string
  name: string
  description: string | null
  status: 'created' | 'analyzing' | 'completed' | 'failed'
  event_count: number
  analyzed_at: string | null
  created_at: string
  updated_at: string
}

export interface UploadResult {
  events_added: number
}

export interface CustomerResult {
  customer_id: string
  segment: string
  r_score: number
  f_score: number
  m_score: number
  recency_days: number
  frequency: number
  monetary: number
}

export interface AnalysisResult {
  unique_customers: number
  segment_counts: Record<string, number>
  customers: CustomerResult[]
}
