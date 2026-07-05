export interface MemoryOverviewCopy {
  title: string
  description: string
  hint: string
}

export interface MemoryRecord {
  id: number
  text: string
  summary: string | null
  tags: string | null
  confidence: number
  recency_score: number
  memory_type: string | null
  keywords: string | null
  source: string | null
  conversation_id: number | null
  similarity?: number
  created_at: string | null
}
