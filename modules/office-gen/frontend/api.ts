import { apiGet, apiPost } from '../runtime'

export type OfficeFormat = 'docx' | 'xlsx' | 'pptx' | 'pdf'

export interface GeneratedFile {
  file_id: number
  name: string
  extension: string
  size: number
  mime_type: string
  deduplicated?: boolean
}

export interface GeneratedArtifact {
  artifact_id: number
  file_id: number
  content_package_id: number | null
  content_package_status: string
  content_package_error: string | null
  format: OfficeFormat
  name: string
  extension: string
  size: number
  status: string
}

interface ModuleCallPayload {
  target_module: string
  action: string
  parameters: Record<string, unknown>
}

export async function checkHealth(): Promise<{ libreoffice: boolean }> {
  return apiGet('/office-gen/health')
}

function buildSamplePayload(format: OfficeFormat, filename: string): Record<string, unknown> {
  if (format === 'xlsx') {
    return {
      filename,
      sheets: [{
        name: 'Summary',
        columns: ['item', 'count'],
        rows: [
          ['Alpha', 1],
          ['Beta', 2],
        ],
      }],
    }
  }

  if (format === 'pptx') {
    return {
      filename,
      slides: [{
        title: 'Office Gen Sample',
        bullets: ['Generated through the module HTTP endpoint', 'Saved by the framework file service'],
      }],
    }
  }

  const content = [
    { type: 'heading', text: 'Office Gen Sample', level: 1 },
    { type: 'paragraph', text: 'Generated through the module HTTP endpoint.' },
    { type: 'table', header: ['item', 'count'], rows: [['Alpha', 1], ['Beta', 2]] },
  ]
  return { filename, content }
}

function sampleFilename(format: OfficeFormat, prefix: string): string {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const cleanPrefix = prefix.trim()
  if (!cleanPrefix) throw new Error('Filename prefix is required')
  return `${cleanPrefix}-${format}-${stamp}`
}

export async function generateSample(format: OfficeFormat, prefix = 'office-gen-sample'): Promise<GeneratedFile> {
  const filename = sampleFilename(format, prefix)
  return apiPost<GeneratedFile>(`/office-gen/${format}`, buildSamplePayload(format, filename))
}

export async function generateArtifactSample(format: OfficeFormat, prefix = 'office-gen-artifact'): Promise<GeneratedArtifact> {
  const filename = sampleFilename(format, prefix)
  const payload = buildSamplePayload(format, filename)
  return apiPost<GeneratedArtifact>('/modules/call', {
    target_module: 'office-gen',
    action: 'generate_to_artifact',
    parameters: {
      format,
      ...payload,
    },
  } satisfies ModuleCallPayload)
}
