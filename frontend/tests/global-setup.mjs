import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const AUTH_DIR = path.resolve(__dirname, '.auth')

const ACCOUNTS = [
  { role: 'admin', username: '何焜华', password: '123rgE123', storageFile: 'admin.json' },
  { role: 'viewer', username: 'viewer', password: 'admin123', storageFile: 'viewer.json' },
]

async function globalSetup() {
  fs.mkdirSync(AUTH_DIR, { recursive: true })

  const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173'
  const origin = new URL(baseURL).origin

  for (const acct of ACCOUNTS) {
    const resp = await fetch(`${baseURL}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: acct.username, password: acct.password }),
    })
    const body = await resp.json()
    const token = body?.data?.access_token
    if (!resp.ok || !token) {
      throw new Error(`Failed to create ${acct.role} storageState: ${JSON.stringify(body).slice(0, 300)}`)
    }
    const storageState = {
      cookies: [],
      origins: [{
        origin,
        localStorage: [{ name: 'v2_auth_token', value: token }],
      }],
    }
    fs.writeFileSync(path.join(AUTH_DIR, acct.storageFile), JSON.stringify(storageState, null, 2), 'utf-8')
  }
}

export default globalSetup
