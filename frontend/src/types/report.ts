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
