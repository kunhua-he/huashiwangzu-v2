import { getAppRegistry } from '@/desktop/app-registry/desktop-app-state'
import { getAllowedApps } from './app-registry'

interface FileAssociationResult {
  appKey: string
  editable: boolean
  category: string
  categoryLabel: string
}

const categoryLabelMap: Record<string, string> = {
  image: 'Image', document: 'Document', text: 'Text', table: 'Table',
  code: 'Code', audio: 'Audio', video: 'Video', legacy: 'Legacy format',
  presentation: 'Presentation', unknown: 'Unknown type',
}

const legacyCategoryLabelMap: Record<string, string> = {
  doc: 'Legacy Word', xls: 'Legacy Excel', ppt: 'Legacy PPT',
  vsd: 'Visio', vsdx: 'Visio', mpp: 'Project', zip: 'Archive', rar: 'Archive',
}

const legacyReadonlyExtensions = ['doc', 'xls', 'ppt', 'vsd', 'vsdx', 'mpp', 'zip', 'rar']

export function getAppByFileFormat(format: string, role?: string): FileAssociationResult {
  const ext = (format || '').toLowerCase().replace(/^\./, '')
  if (!ext) return { appKey: 'filePreview', editable: false, category: 'unknown', categoryLabel: 'Unknown type' }

  if (legacyReadonlyExtensions.includes(ext)) {
    return { appKey: 'filePreview', editable: false, category: 'legacy', categoryLabel: legacyCategoryLabelMap[ext] || 'Legacy format' }
  }

  const appList = role ? getAllowedApps(role) : Object.values(getAppRegistry())
  for (const app of appList) {
    const formatList = app.supportedFileFormats
    if (!formatList) continue
    if (formatList.includes(ext)) {
      const isEditable = app.appKey !== 'filePreview'
      const category = inferFormatCategory(ext, app.appKey)
      return { appKey: app.appKey, editable: isEditable, category, categoryLabel: categoryLabelMap[category] || ext.toUpperCase() }
    }
  }

  return { appKey: 'filePreview', editable: false, category: 'unknown', categoryLabel: 'Unknown type' }
}

function inferFormatCategory(ext: string, appKey: string): string {
  if (appKey === 'filePreview') {
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico', 'svg'].includes(ext)) return 'image'
    if (['mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a'].includes(ext)) return 'audio'
    if (['mp4', 'webm', 'mov', 'm4v'].includes(ext)) return 'video'
    if (ext === 'pdf') return 'document'
  }
  if (appKey === 'textEditor') return ['txt', 'md'].includes(ext) ? 'text' : 'code'
  if (appKey === 'csvEditor') return 'table'
  if (appKey === 'excelEditor') return 'table'
  if (appKey === 'docxEditor') return 'document'
  if (appKey === 'pptxEditor') return 'presentation'
  return 'document'
}

export function getFileAppKey(format: string, role?: string): string {
  return getAppByFileFormat(format, role).appKey
}

export function getFileCategoryLabel(format: string, role?: string): string {
  return getAppByFileFormat(format, role).categoryLabel
}

export function isFormatEditable(format: string, role?: string): boolean {
  return getAppByFileFormat(format, role).editable
}
