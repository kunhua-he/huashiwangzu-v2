import type { EvidenceReference } from './evidenceReferences'

export interface ToolInfoLike {
  name?: string
  effective_tool_name?: string
  tool_call_id?: string
}

export interface ToolNodeLike {
  toolName?: string
  node?: string
  status?: string
  targetTool?: string
  elapsedMs?: number
}

export interface ToolParameterRow {
  name: string
  type: string
  description: string
  required: boolean
}

export interface ToolResultSummary {
  kind: 'skills' | 'schema' | 'file-open' | 'images' | 'text' | 'object' | 'empty'
  title: string
  status: 'success' | 'failed' | 'neutral'
  description?: string
  skills?: Array<{ name: string; displayName: string; brief: string }>
  parameters?: ToolParameterRow[]
  fields?: Array<{ label: string; value: string }>
}

export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  skill_list: '查看技能列表',
  skill_describe: '查看技能说明',
  skill_use: '调用技能',
  knowledge__search: '检索知识库',
  knowledge__get_block: '读取知识块',
  web_tools__search: '联网搜索',
  'docs-open__open': '打开文档',
  'docs-open__get_content': '获取文档内容',
  'docs-open__create_doc': '创建文档',
  'desktop-tools__list_files': '列出桌面文件',
  'desktop-tools__search_files': '搜索桌面文件',
  'desktop-tools__read_file': '读取桌面文件',
  'desktop-tools__get_file': '获取文件详情',
  'desktop-tools__open_file': '打开桌面文件',
  'desktop-tools__list_apps': '列出桌面应用',
  'desktop-tools__create_file': '创建文件',
  'desktop-tools__replace_file': '替换文件内容',
  'desktop-tools__delete_file': '删除文件',
  'desktop-tools__rename_file': '重命名文件',
  'desktop-tools__copy_file': '复制文件',
  'desktop-tools__list_versions': '列出文件版本',
  'desktop-tools__restore_version': '恢复文件版本',
  'desktop-tools__publish_artifact': '发布制品到桌面',
  'desktop-tools__refresh': '刷新桌面',
  'media-asr__extract_audio': '提取视频音频',
  'media-asr__transcribe_audio': '音频转文字',
  'media-asr__transcribe_video': '视频转文字',
}

const LOW_LEVEL_NODES = new Set(['tool_execution', 'policy_check'])

export function displayToolName(name?: string): string {
  const normalized = name?.trim() || ''
  return TOOL_DISPLAY_NAMES[normalized] || normalized || '未知工具'
}

export function effectiveToolName(tool: ToolInfoLike): string {
  return tool.effective_tool_name?.trim() || tool.name?.trim() || 'unknown'
}

export function semanticNodeName(node: ToolNodeLike): string {
  const target = node.targetTool?.trim() || node.toolName?.trim() || node.node?.trim() || 'unknown'
  if (node.node === 'skill_use' && node.targetTool) return node.targetTool
  if (node.node && !LOW_LEVEL_NODES.has(node.node)) return node.node
  return target
}

export function isLowLevelNode(node: ToolNodeLike): boolean {
  return LOW_LEVEL_NODES.has(node.node || '')
}

export function statusText(status?: string): string {
  if (status === 'started') return '进行中'
  if (status === 'completed') return '完成'
  if (status === 'timeout') return '超时'
  if (status === 'failed') return '失败'
  if (status === 'blocked') return '已拦截'
  return status || '处理中'
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))}ms`
  const sec = ms / 1000
  if (sec < 60) return `${Number(sec.toFixed(sec < 10 ? 1 : 0))}秒`
  const minutes = Math.floor(sec / 60)
  const rest = Math.round(sec % 60)
  return `${minutes}分${rest}秒`
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

export function resultPayload(result: unknown): unknown {
  if (!isRecord(result)) return result
  return isRecord(result.data) ? result.data : result
}

export function isFailureResult(result: unknown, toolStatus?: string): boolean {
  if (toolStatus === 'failed') return true
  if (!isRecord(result)) return false
  if (result.success === false || result.error || result.denied || result.policy_blocked) return true
  const inner = resultPayload(result)
  return isRecord(inner) && (inner.success === false || !!inner.error)
}

export function summarizeToolResult(toolName: string, result: unknown, toolStatus?: string): ToolResultSummary {
  const payload = resultPayload(result)
  const failed = isFailureResult(result, toolStatus)
  const error = extractErrorText(result)
  if (failed) {
    return {
      kind: 'text',
      title: `${displayToolName(toolName)}失败`,
      status: 'failed',
      description: error || '工具返回失败状态',
    }
  }
  if (toolName === 'skill_list') return summarizeSkillList(payload)
  if (toolName === 'skill_describe') return summarizeSkillDescribe(payload)
  if (toolName === 'desktop-tools__open_file') return summarizeFileOpen(payload)
  if (hasGeneratedImages(payload)) {
    return { kind: 'images', title: '生成图片', status: 'success', description: '已生成图片，可点击缩略图打开。' }
  }
  if (typeof payload === 'string') {
    return { kind: 'text', title: `${displayToolName(toolName)}完成`, status: 'success', description: payload }
  }
  if (!isRecord(payload)) {
    return { kind: payload == null ? 'empty' : 'text', title: `${displayToolName(toolName)}完成`, status: 'success', description: payload == null ? '工具未返回可展示内容' : String(payload) }
  }
  return summarizeGenericObject(toolName, payload)
}

export function compactReferenceText(refs: EvidenceReference[]): string {
  if (!refs.length) return ''
  const first = refs[0]
  const title = first.title || `${first.ref_key} ${first.ref_id}`
  return refs.length === 1 ? `引用 ${title}` : `引用 ${title} 等 ${refs.length} 项`
}

function summarizeSkillList(payload: unknown): ToolResultSummary {
  const obj = isRecord(payload) ? payload : {}
  const skills = Array.isArray(obj.skills)
    ? obj.skills.filter(isRecord).map(skill => ({
      name: stringField(skill, 'name') || 'unknown',
      displayName: stringField(skill, 'display_name') || stringField(skill, 'displayName') || stringField(skill, 'name') || '未知工具',
      brief: stringField(skill, 'brief') || stringField(skill, 'description') || '',
    }))
    : []
  const total = Number(obj.total) || skills.length
  return {
    kind: 'skills',
    title: `可用工具 ${total} 个`,
    status: 'success',
    description: skills.length ? '已读取当前可调用工具。' : '没有返回工具列表。',
    skills,
  }
}

function summarizeSkillDescribe(payload: unknown): ToolResultSummary {
  if (!isRecord(payload)) {
    return { kind: 'text', title: '工具说明', status: 'success', description: String(payload ?? '') }
  }
  const name = stringField(payload, 'name') || 'unknown'
  const description = stringField(payload, 'description') || stringField(payload, 'brief') || ''
  const parameters = parameterRows(payload.parameters)
  return {
    kind: 'schema',
    title: displayToolName(name),
    status: 'success',
    description,
    parameters,
    fields: [
      { label: '工具名', value: name },
      { label: '模块', value: stringField(payload, 'module') || '-' },
      { label: '动作', value: stringField(payload, 'action') || '-' },
      { label: '权限', value: stringField(payload, 'min_role') || '-' },
    ],
  }
}

function summarizeFileOpen(payload: unknown): ToolResultSummary {
  const obj = isRecord(payload) ? payload : {}
  const fileId = scalarText(obj.file_id)
  const fileName = stringField(obj, 'file_name') || stringField(obj, 'name') || (fileId ? `文件 ${fileId}` : '文件')
  const format = stringField(obj, 'format') || stringField(obj, 'mime_type') || ''
  return {
    kind: 'file-open',
    title: '已打开桌面文件',
    status: 'success',
    description: `${fileName}${format ? ` · ${format}` : ''}${fileId ? ` · ID ${fileId}` : ''}`,
    fields: [
      { label: '文件', value: fileName },
      { label: 'ID', value: fileId || '-' },
      { label: '格式', value: format || '-' },
    ],
  }
}

function summarizeGenericObject(toolName: string, payload: Record<string, unknown>): ToolResultSummary {
  const fields = Object.entries(payload)
    .filter(([, value]) => value !== undefined && value !== null && typeof value !== 'object')
    .slice(0, 6)
    .map(([label, value]) => ({ label, value: scalarText(value) || '' }))
  const count = Object.keys(payload).length
  return {
    kind: 'object',
    title: `${displayToolName(toolName)}完成`,
    status: 'success',
    description: fields.length ? `返回 ${count} 个字段。` : '工具返回结构化数据。',
    fields,
  }
}

function parameterRows(parameters: unknown): ToolParameterRow[] {
  if (!isRecord(parameters)) return []
  const props = isRecord(parameters.properties) ? parameters.properties : {}
  const required = Array.isArray(parameters.required) ? new Set(parameters.required.filter(value => typeof value === 'string')) : new Set<string>()
  return Object.entries(props).filter(([, value]) => isRecord(value)).map(([name, value]) => {
    const schema = value as Record<string, unknown>
    return {
      name,
      type: stringField(schema, 'type') || 'object',
      description: stringField(schema, 'description') || '',
      required: required.has(name),
    }
  })
}

function hasGeneratedImages(payload: unknown): boolean {
  if (!isRecord(payload)) return false
  if (isImageEntry(payload)) return true
  return Array.isArray(payload.images) && payload.images.some(isImageEntry)
}

function isImageEntry(value: unknown): boolean {
  return isRecord(value) && typeof value.file_id === 'number' && (value.type === undefined || value.type === 'image')
}

function extractErrorText(result: unknown): string {
  if (!isRecord(result)) return ''
  const payload = resultPayload(result)
  const direct = stringField(result, 'error') || stringField(result, 'message')
  if (direct) return direct
  return isRecord(payload) ? (stringField(payload, 'error') || stringField(payload, 'message') || '') : ''
}

function stringField(record: Record<string, unknown>, key: string): string {
  const value = record[key]
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

function scalarText(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}
