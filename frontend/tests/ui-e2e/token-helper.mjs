import fs from 'fs'
import path from 'path'
import { execFileSync } from 'child_process'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '../../..')
const BACKEND_PYTHON = path.join(REPO_ROOT, 'backend/.venv/bin/python')
const AUTH_TOKEN_SCRIPT = path.join(REPO_ROOT, 'dev_toolkit/auth_token.py')

export function issueLocalToken(role = 'admin') {
  const python = fs.existsSync(BACKEND_PYTHON) ? BACKEND_PYTHON : 'python3.14'
  const stdout = execFileSync(
    python,
    [AUTH_TOKEN_SCRIPT, '--role', role, '--repo-root', REPO_ROOT],
    { cwd: REPO_ROOT, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'pipe'] },
  )
  const payload = JSON.parse(stdout)
  if (!payload?.access_token) {
    throw new Error(`Local token helper returned no token for ${role}`)
  }
  return payload.access_token
}

export function storageStateForToken(baseURL, token) {
  return {
    cookies: [],
    origins: [{
      origin: new URL(baseURL).origin,
      localStorage: [{ name: 'v2_auth_token', value: token }],
    }],
  }
}
