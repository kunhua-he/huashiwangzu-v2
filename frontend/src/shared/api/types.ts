export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T | null
  error?: string | null
  errors?: { field: string; message: string }[] | null
}

export interface LoginParams {
  username: string
  password: string
}

export interface UserInfo {
  userId?: number
  username?: string
  displayName?: string
  email?: string
  role?: string
}

export interface MenuItem {
  name: string
  path: string
  icon: string
}

export interface PaginatedResult<T> {
  current_page: number
  data: T[]
  last_page: number
  per_page: number
  total: number
}

export interface SystemStatusEntry {
  status: boolean
  message: string
}

export interface SystemStatus {
  backend: SystemStatusEntry
  database: SystemStatusEntry
  worker: SystemStatusEntry
  modelService: SystemStatusEntry
  productionEntry: SystemStatusEntry
}

export type {
  FolderEntry, FileEntry, RecycleBinEntry, FileDetail,
  DashboardOverview, LogEntry, TaskItem,
  SystemConfig, RoleMatrixItem,
  AgentSessionEntry, ChatMessageEntry,
  KnowledgeEntry, CatalogEntry, KnowledgeTaskEntry, KnowledgeProgress, FileParseResult,
  NotificationItem, SystemLogEntry,
} from './common-data-types'

export interface WeakTypeItem {
  type: string
  count: number
  avg_recall: number
}

export interface EvalRecord {
  record_id: number
  total_questions: number
  answered_count: number
  unanswered_count: number
  recall_rate: number
  MRR: number
  NDCG: number
  evidence_hit_rate: number
  refusal_accuracy: number
  weak_types: WeakTypeItem[]
  detail_items?: EvalQuestionDetail[]
  duration_ms: number
  created_at: string
}

export interface EvalQuestionDetail {
  /** 查询或提问内容：用于构建提示词 */
  question: string
  /** 标准答案文本：LLM 回答质量的参照 */
  expected_answer: string
  /** 实际回答文本：LLM 的原始输出 */
  llm_answer?: string
  /** 回答是否相关 / 得分 */
  is_relevant?: boolean
  /** 关联到知识库的文档 ID */
  document_id?: number
  /** 创建时间 */
  created_at?: string
}

export type EvalRecordBrief = Omit<EvalRecord, 'detail_items'>
