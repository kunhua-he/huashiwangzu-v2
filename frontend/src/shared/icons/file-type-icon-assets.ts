const folderIcon = '<svg viewBox="0 0 64 52" xmlns="http://www.w3.org/2000/svg"><path d="M6 12c0-3.3 2.7-6 6-6h12l5 5h23c3.3 0 6 2.7 6 6v4H6v-9z" fill="#9ed0ff"/><path d="M4 18c0-3.3 2.7-6 6-6h44c3.3 0 6 2.7 6 6v20c0 4.4-3.6 8-8 8H12c-4.4 0-8-3.6-8-8V18z" fill="#5aa7ff"/><path d="M7 21h50v3H7z" fill="#cfe7ff" opacity=".65"/></svg>'
const defaultDoc = '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><path d="M16 6h24l10 10v36c0 3.3-2.7 6-6 6H16c-3.3 0-6-2.7-6-6V12c0-3.3 2.7-6 6-6z" fill="#fff" stroke="#d9e2ec" stroke-width="2"/><path d="M40 6v12h12" fill="#eef4fa"/><path d="M18 28h28M18 36h28M18 44h18" stroke="#94a3b8" stroke-width="4" stroke-linecap="round"/></svg>'
const notepadIcon = '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><rect x="12" y="10" width="40" height="48" rx="6" fill="#7dd3fc"/><rect x="12" y="52" width="40" height="6" rx="2" fill="#d97706" opacity=".75"/><path d="M20 10v-4M28 10v-4M36 10v-4M44 10v-4" stroke="#0f172a" stroke-width="4" stroke-linecap="round"/><path d="M21 26h22M21 34h22M21 42h16" stroke="#0c4a6e" stroke-width="4" stroke-linecap="round" opacity=".78"/></svg>'

function buildBadgeDoc(background: string, label: string, line: string) {
  return `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><path d="M16 6h24l10 10v36c0 3.3-2.7 6-6 6H16c-3.3 0-6-2.7-6-6V12c0-3.3 2.7-6 6-6z" fill="#fff" stroke="#d9e2ec" stroke-width="2"/><path d="M40 6v12h12" fill="#eef4fa"/><rect x="14" y="14" width="28" height="12" rx="6" fill="${background}"/><text x="28" y="22.5" text-anchor="middle" font-size="8.5" font-weight="700" font-family="Arial, sans-serif" fill="#fff">${label}</text><path d="M18 34h24M18 42h24M18 50h16" stroke="${line}" stroke-width="4" stroke-linecap="round" opacity=".7"/></svg>`
}

const wordIcon = buildBadgeDoc('#185abd', 'WORD', '#185abd')
const excelIcon = buildBadgeDoc('#107c41', 'XLS', '#107c41')
const pptIcon = buildBadgeDoc('#f43f5e', 'PPT', '#f43f5e')

const fileIconMap: Record<string, string> = {
  txt: notepadIcon, log: notepadIcon, md: notepadIcon,
  doc: wordIcon, docx: wordIcon,
  xls: excelIcon, xlsx: excelIcon, csv: excelIcon,
  ppt: pptIcon, pptx: pptIcon,
  pdf: buildBadgeDoc('#dc2626', 'PDF', '#dc2626'),
  png: buildBadgeDoc('#0ea5e9', 'PNG', '#0ea5e9'),
  jpg: buildBadgeDoc('#7c3aed', 'JPG', '#7c3aed'),
  jpeg: buildBadgeDoc('#7c3aed', 'JPG', '#7c3aed'),
  webp: buildBadgeDoc('#7c3aed', 'IMG', '#7c3aed'),
  zip: buildBadgeDoc('#f59e0b', 'ZIP', '#b45309'),
}

export function getFileTypeSVG(kind: 'file' | 'folder', extension = ''): string {
  if (kind === 'folder') return folderIcon
  return fileIconMap[extension.toLowerCase()] || defaultDoc
}
