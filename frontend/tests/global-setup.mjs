import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'
import { issueLocalToken, storageStateForToken } from './ui-e2e/token-helper.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const AUTH_DIR = path.resolve(__dirname, '.auth')

const ACCOUNTS = [
  { role: 'admin', storageFile: 'admin.json' },
  { role: 'viewer', storageFile: 'viewer.json' },
]

async function globalSetup() {
  fs.mkdirSync(AUTH_DIR, { recursive: true })

  const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173'

  for (const acct of ACCOUNTS) {
    const token = issueLocalToken(acct.role)
    const storageState = storageStateForToken(baseURL, token)
    fs.writeFileSync(path.join(AUTH_DIR, acct.storageFile), JSON.stringify(storageState, null, 2), 'utf-8')
  }
}

export default globalSetup
