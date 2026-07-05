import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

export const TEST_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const REPO_ROOT = path.resolve(TEST_DIR, '../..')
export const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173'
export const SCREENSHOT_DIR = path.resolve(process.env.HOME || '/tmp', 'Downloads/ui-e2e')
export const MANUAL_SCREENSHOTS_ENABLED = process.env.UI_E2E_SCREENSHOTS === '1'
export const ADMIN_STORAGE_FILE = path.join(TEST_DIR, '.auth/admin.json')
export const TS = Date.now()
export const DEFAULT_REPORT_PATH = path.resolve(
  REPO_ROOT,
  '../华世王镞_v2邮箱/收件箱/前端UI集测/审核报告.md',
)

export const results = []
export const consoleCollector = []
export const uploadedFilesById = new Map()

export function attachConsoleCollector(page) {
  consoleCollector.length = 0
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      consoleCollector.push(`${msg.type()}: ${msg.text()}`)
    }
  })
}

export async function screenshot(page, name) {
  if (!MANUAL_SCREENSHOTS_ENABLED) return ''
  const filePath = path.join(SCREENSHOT_DIR, `${name}.png`)
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  await page.screenshot({ path: filePath, fullPage: false })
  return filePath
}
