import fs from 'fs'

import { ADMIN_STORAGE_FILE, BASE_URL } from './state.mjs'

export const ADMIN_USER = '何焜华'
export const ADMIN_PASS = '123rgE123'

let adminTokenOverride = null
let adminRefreshPromise = null

async function isAdminTokenValid(token) {
  if (!token) return false
  const resp = await fetch(`${BASE_URL}/api/current-user`, {
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => null)
  return Boolean(resp?.ok)
}

function writeAdminStorageState(token) {
  const storageState = {
    cookies: [],
    origins: [{
      origin: new URL(BASE_URL).origin,
      localStorage: [{ name: 'v2_auth_token', value: token }],
    }],
  }
  fs.writeFileSync(ADMIN_STORAGE_FILE, JSON.stringify(storageState, null, 2), 'utf-8')
}

function readAdminStorageToken() {
  const storage = JSON.parse(fs.readFileSync(ADMIN_STORAGE_FILE, 'utf-8'))
  const origin = new URL(BASE_URL).origin
  const state = storage.origins?.find(item => item.origin === origin) || storage.origins?.[0]
  return state?.localStorage?.find(item => item.name === 'v2_auth_token')?.value || ''
}

export async function refreshAdminStorageState() {
  if (adminTokenOverride && await isAdminTokenValid(adminTokenOverride)) return adminTokenOverride

  const storedToken = readAdminStorageToken()
  if (await isAdminTokenValid(storedToken)) {
    adminTokenOverride = storedToken
    return storedToken
  }

  const resp = await fetch(`${BASE_URL}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: ADMIN_USER, password: ADMIN_PASS }),
  })
  const body = await resp.json()
  const token = body?.data?.access_token
  if (!resp.ok || !token) {
    throw new Error(`Admin API login failed: ${JSON.stringify(body).slice(0, 300)}`)
  }
  adminTokenOverride = token
  writeAdminStorageState(token)
  return token
}

export async function refreshAdminToken() {
  if (!adminRefreshPromise) {
    adminRefreshPromise = refreshAdminStorageState().finally(() => {
      adminRefreshPromise = null
    })
  }
  return adminRefreshPromise
}

export async function getAuthToken() {
  if (adminTokenOverride) return adminTokenOverride
  const token = readAdminStorageToken()
  if (!token) throw new Error('Admin storageState has no v2_auth_token')
  return token
}

export async function requestWithAdminAuthRetry(token, makeRequest) {
  let activeToken = adminTokenOverride || token
  let response = await makeRequest(activeToken)
  for (let attempt = 0; response.status() === 401 && attempt < 5; attempt++) {
    activeToken = await refreshAdminToken()
    response = await makeRequest(activeToken)
  }
  return response
}
