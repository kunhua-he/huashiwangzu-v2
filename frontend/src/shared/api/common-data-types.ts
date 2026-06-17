export interface FolderEntry {
  id: number
  name: string
  parent_folder_id: number | null
}
export interface FileParseResult {
  [key: string]: unknown
}

export interface NotificationItem {
  id: number
  title: string
  type: string
  is_read: boolean
  published_at: string
  [key: string]: unknown
}

export interface SystemLogEntry {
  id: number
  level: string
  category: string
  message: string
  created_at: string
  [key: string]: unknown
}
export interface FileEntry {
  id: number
  file_name: string
  format: string | null
  file_size: number
  created_at: string
  storage_path: string | null
  is_folder?: boolean
  parent_folder_id?: number | null
}

export interface RecycleBinEntry {
  id: number
  name: string
  type: 'file' | 'folder'
  format: string
  size: number
  original_folder_id: number | null
  deleted_at: string
}

export interface FileDetail {
  id: number
  file_name: string
  format: string
  file_size: number
  folder_id: number
  folder_name: string
  created_at: string
  updated_at: string
  storage_path: string
  is_deleted: boolean
}

export interface DashboardOverview {
  system_version?: string
  project_name?: string
  total_users?: number
  online_users?: number
  total_files?: number
  agent_session_count?: number
  knowledge_file_count?: number
}

export interface LogEntry {
  id: number
  level: string
  category: string
  message: string
  created_at: string
}

export interface TaskItem {
  id: number
  task_type: string
  module_name: string
  status: string
  priority: number
  params: string | null
  result: string | null
  error_message: string | null
  retry_count: number
  max_retries: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  creator_id: number | null
}

export interface SystemConfig {
  project_name: string
  system_version: string
  login_page_title: string
  default_role: string
}

export interface RoleMatrixItem {
  role: string
  name: string
  user_management: boolean
  system_config: boolean
  role_matrix: boolean
}

export interface AgentSessionEntry {
  id: number
  session_key: string
  title: string
  message_count: number
  created_at: string
}
export interface ChatMessageEntry {
  id: number
  type: string
  content: string
  thinking_content?: string
  created_at: string
}

export interface KnowledgeEntry {
  chunk_id: number; title: string; summary: string; file_id: number
  file_name: string | null; doc_type: string | null; format?: string | null; category: string | null; created_at: string
  score?: number; source_type?: string; ranking_explanation?: string; page_number?: number
  match_detail?: Record<string, unknown> | null
  content_text?: string; page_title?: string; page_summary?: string
  body_json?: string | null; attributes_json?: string | null; tags_json?: string | null
  folder_id?: number; path_ids?: number[]; fusion_id?: number; processing_status?: string | null
}

export interface CatalogEntry {
  file_id: number; file_name: string | null; format: string | null
  category: string | null; doc_type: string | null; channel: string | null
  processing_status: string | null; error_message: string | null; cataloged_at: string | null
  progress?: KnowledgeProgress
}

export interface KnowledgeTaskEntry {
  task_id: number; file_id: number; file_name: string | null; channel: string | null
  priority: number; status: string; enqueued_at: string
  started_at: string | null; ended_at: string | null; error_message: string | null
  progress?: KnowledgeProgress
}

export interface KnowledgeProgress {
  percent: number; current_step: string; chunk_count: number; candidate_count: number; evidence_count: number
  phase_list: Array<{ name: string; status: string }>
}
