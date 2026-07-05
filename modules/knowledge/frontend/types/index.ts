export interface KnowledgeEntryProps {
  documentId?: number
  view?: string
  showGovernance?: boolean
}

export type {
  DashboardStats,
  DocProgressEntry,
  DocumentProfile,
  DocumentProgress,
  EntityGraph,
  EntityGraphEdge,
  EntityGraphNode,
  ExportFormat,
  ExportResult,
  FileRelation,
  FileTreeNode,
  FusionPage,
  GovernanceCandidate,
  GovernanceCandidateList,
  KnowledgeDocument,
  KnowledgeIngestStatus,
  ProgressStage,
  RelationGraph,
  RelationGraphEdge,
  RelationGraphNode,
  SearchResult,
} from '../api'
export type { GraphNode } from '../graph3d/types'
