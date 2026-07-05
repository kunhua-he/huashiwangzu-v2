import fs from 'fs'
import path from 'path'

import { REPO_ROOT, TS } from './state.mjs'

export const SAMPLE_FILES = {
  docx: path.join(REPO_ROOT, 'modules/docx-parser/sandbox/samples/sample.docx'),
  pptx: path.join(REPO_ROOT, 'modules/pptx-parser/sandbox/samples/sample.pptx'),
  xlsx: path.join(REPO_ROOT, 'modules/xlsx-parser/sandbox/samples/sample.xlsx'),
}

export function minimalPdf(text = 'Hello PDF') {
  return `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 50 700 Td (${text}) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000360 00000 n 
trailer<</Size 6/Root 1 0 R>>
startxref
437
%%EOF`
}

export function minimalPng() {
  const buf = Buffer.alloc(67)
  buf.write('\\x89PNG\\r\\n\\x1a\\n', 0)
  buf.writeUInt32BE(13, 8)
  buf.write('IHDR', 12)
  buf.writeUInt32BE(1, 16)
  buf.writeUInt32BE(1, 20)
  buf[24] = 8
  buf[25] = 2
  buf[29] = 0
  buf[30] = 0
  buf[31] = 0
  buf.write('IDAT', 45)
  buf.write('IEND', 58)
  return buf
}

export function viewerSamples() {
  return [
    {
      key: 'txt',
      fileName: `e2e-${TS}-test.txt`,
      mimeType: 'text/plain',
      content: 'Hello E2E test file.\nLine 2中文内容\nLine 3',
      expectedApp: 'text-editor',
    },
    {
      key: 'pdf',
      fileName: `e2e-${TS}-test.pdf`,
      mimeType: 'application/pdf',
      content: minimalPdf('E2E PDF Test'),
      expectedApp: 'pdf-viewer',
    },
    {
      key: 'png',
      fileName: `e2e-${TS}-test.png`,
      mimeType: 'image/png',
      content: minimalPng(),
      expectedApp: 'image-viewer',
    },
    {
      key: 'docx',
      fileName: `e2e-${TS}-test.docx`,
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      content: fs.readFileSync(SAMPLE_FILES.docx),
      expectedApp: 'doc-viewer',
    },
    {
      key: 'pptx',
      fileName: `e2e-${TS}-test.pptx`,
      mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      content: fs.readFileSync(SAMPLE_FILES.pptx),
      expectedApp: 'ppt-viewer',
    },
    {
      key: 'xlsx',
      fileName: `e2e-${TS}-test.xlsx`,
      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      content: fs.readFileSync(SAMPLE_FILES.xlsx),
      expectedApp: 'excel-engine',
    },
  ]
}
