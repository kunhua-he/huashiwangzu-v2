import { expect } from '@playwright/test'

import { BASE_URL, uploadedFilesById } from './state.mjs'
import { refreshAdminToken, requestWithAdminAuthRetry } from './auth.mjs'

export async function uploadSample(request, token, name, mimeType, content, folderId = 0) {
  const uploadResp = await requestWithAdminAuthRetry(token, (activeToken) => request.post(`${BASE_URL}/api/files/upload`, {
    headers: { Authorization: `Bearer ${activeToken}` },
    multipart: {
      file: { name, mimeType, buffer: Buffer.from(content) },
      folder_id: String(folderId),
    },
  }))
  const body = await uploadResp.json().catch(() => ({}))
  if (!uploadResp.ok() || body.success !== true) {
    throw new Error(`Upload failed: status=${uploadResp.status()}, error=${body.error || JSON.stringify(body).slice(0, 200)}`)
  }
  const fileId = fileIdFromUpload(body.data)
  if (fileId !== undefined && fileId !== null) {
    uploadedFilesById.set(String(fileId), { fileId, fileName: name })
  }
  return body.data
}

export function fileIdFromUpload(data) {
  return data?.id ?? data?.file_id
}

export function fileItemMatches(item, fileId, fileName) {
  const ids = [item?.id, item?.file_id, item?.original_file_id]
    .filter(value => value !== undefined && value !== null)
    .map(value => String(value))
  const names = [item?.name, item?.file_name, item?.original_name]
    .filter(Boolean)
    .map(value => String(value))
  return ids.includes(String(fileId)) || names.includes(fileName)
}

export function recycleItemMatches(item, fileId, fileName) {
  const ids = [item?.origin_id, item?.file_id, item?.original_file_id]
    .filter(value => value !== undefined && value !== null)
    .map(value => String(value))
  const names = [item?.name, item?.file_name, item?.original_name]
    .filter(Boolean)
    .map(value => String(value))
  return ids.includes(String(fileId)) || names.includes(fileName)
}

function responseItemsOrThrow(body, context) {
  if (body?.success !== true) {
    throw new Error(`${context} failed: ${body?.error || JSON.stringify(body).slice(0, 200)}`)
  }
  const items = body?.data?.items ?? body?.data
  if (!Array.isArray(items)) {
    throw new Error(`${context} returned non-list data: ${JSON.stringify(body?.data).slice(0, 200)}`)
  }
  return items
}

export async function readActiveFileItems(request, token, fileName) {
  const searchResp = await requestWithAdminAuthRetry(token, (activeToken) => request.get(`${BASE_URL}/api/files/search?keyword=${encodeURIComponent(fileName)}&page=1&page_size=50`, {
    headers: { Authorization: `Bearer ${activeToken}` },
  }))
  const searchBody = await searchResp.json().catch(() => ({}))
  if (!searchResp.ok()) {
    throw new Error(`Active file search failed: status=${searchResp.status()}, body=${JSON.stringify(searchBody).slice(0, 200)}`)
  }
  const searchItems = responseItemsOrThrow(searchBody, 'Active file search')
  if (searchItems.length > 0) return searchItems

  const listResp = await requestWithAdminAuthRetry(token, (activeToken) => request.get(`${BASE_URL}/api/files/list?folder_id=0&page=1&page_size=200`, {
    headers: { Authorization: `Bearer ${activeToken}` },
  }))
  const listBody = await listResp.json().catch(() => ({}))
  if (!listResp.ok()) {
    throw new Error(`Active file list failed: status=${listResp.status()}, body=${JSON.stringify(listBody).slice(0, 200)}`)
  }
  return responseItemsOrThrow(listBody, 'Active file list')
}

export async function readRecycleItems(request, token) {
  const recycleResp = await requestWithAdminAuthRetry(token, (activeToken) => request.get(`${BASE_URL}/api/recycle/list?page=1&page_size=200`, {
    headers: { Authorization: `Bearer ${activeToken}` },
  }))
  const recycleBody = await recycleResp.json().catch(() => ({}))
  if (!recycleResp.ok()) {
    throw new Error(`Recycle list failed: status=${recycleResp.status()}, body=${JSON.stringify(recycleBody).slice(0, 200)}`)
  }
  return responseItemsOrThrow(recycleBody, 'Recycle list')
}

export async function waitForActiveFileState(request, token, fileId, fileName, expectedVisible) {
  let visible = false
  await expect.poll(async () => {
    const activeItems = await readActiveFileItems(request, token, fileName)
    visible = activeItems.some(item => fileItemMatches(item, fileId, fileName))
    return visible
  }, {
    timeout: 10000,
    intervals: [250, 500, 1000],
  }).toBe(expectedVisible)
  return visible
}

export async function waitForDeletedAndRecycled(request, token, fileId, fileName) {
  const state = { deleted: false, inRecycle: false, recycleItem: null }
  await expect.poll(async () => {
    const [activeItems, recycleItems] = await Promise.all([
      readActiveFileItems(request, token, fileName),
      readRecycleItems(request, token),
    ])
    state.deleted = !activeItems.some(item => fileItemMatches(item, fileId, fileName))
    state.recycleItem = recycleItems.find(item => recycleItemMatches(item, fileId, fileName)) || null
    state.inRecycle = Boolean(state.recycleItem)
    return `${state.deleted}:${state.inRecycle}`
  }, {
    timeout: 10000,
    intervals: [250, 500, 1000],
  }).toBe('true:true')
  return state
}

export async function waitForRecycleFileState(request, token, fileId, fileName, expectedVisible) {
  let visible = false
  await expect.poll(async () => {
    const recycleItems = await readRecycleItems(request, token)
    visible = recycleItems.some(item => recycleItemMatches(item, fileId, fileName))
    return visible
  }, {
    timeout: 10000,
    intervals: [250, 500, 1000],
  }).toBe(expectedVisible)
  return visible
}

export async function cleanupUploadedFiles(request) {
  let token = await refreshAdminToken()
  const trackedFiles = Array.from(uploadedFilesById.values())
  const cleanupFailures = []
  const softDeletedFileIds = new Set()
  let alreadyInactive = 0
  let permanentlyDeleted = 0

  for (const trackedFile of trackedFiles) {
    const { fileId, fileName } = trackedFile
    token = await refreshAdminToken()
    let activeItems = []
    try {
      activeItems = await readActiveFileItems(request, token, fileName)
    } catch (e) {
      cleanupFailures.push(`active query failed for fileId=${fileId}: ${e.message}`)
      continue
    }

    const activeItem = activeItems.find(item => fileItemMatches(item, fileId, fileName))
    if (!activeItem) {
      alreadyInactive++
      continue
    }

    const activeFileId = activeItem.id ?? fileId
    token = await refreshAdminToken()
    const deleteResp = await requestWithAdminAuthRetry(token, (activeToken) => request.post(`${BASE_URL}/api/files/delete`, {
      headers: { Authorization: `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
      data: { id: activeFileId, type: 'file' },
    }))
    const deleteBody = await deleteResp.json().catch(() => ({}))
    if (deleteResp.ok() && deleteBody.success === true) {
      softDeletedFileIds.add(String(fileId))
    } else {
      cleanupFailures.push(`soft delete failed for fileId=${fileId}: status=${deleteResp.status()}, error=${deleteBody.error || JSON.stringify(deleteBody).slice(0, 200)}`)
    }
  }

  let recycleItems = []
  if (softDeletedFileIds.size > 0) {
    try {
      await expect.poll(async () => {
        token = await refreshAdminToken()
        recycleItems = await readRecycleItems(request, token)
        return Array.from(softDeletedFileIds).every(fileId =>
          recycleItems.some(item => recycleItemMatches(item, fileId, uploadedFilesById.get(fileId)?.fileName))
        )
      }, {
        timeout: 10000,
        intervals: [250, 500, 1000],
      }).toBe(true)
    } catch (e) {
      cleanupFailures.push(`recycle list did not include all soft-deleted files: ${e.message}`)
    }
  }

  try {
    token = await refreshAdminToken()
    recycleItems = await readRecycleItems(request, token)
  } catch (e) {
    cleanupFailures.push(`recycle query failed after soft delete: ${e.message}`)
    recycleItems = []
  }

  const trackedRecycleItems = recycleItems.filter(item =>
    trackedFiles.some(({ fileId, fileName }) => recycleItemMatches(item, fileId, fileName))
  )
  const seenRecycleItemIds = new Set()
  for (const recycleItem of trackedRecycleItems) {
    const recycleItemId = recycleItem?.id
    const itemType = recycleItem?.item_type || 'file'
    const originId = recycleItem?.origin_id ?? recycleItem?.file_id ?? recycleItem?.original_file_id ?? null
    if (recycleItemId === undefined || recycleItemId === null) {
      cleanupFailures.push(`recycle item has no recycleItemId: ${JSON.stringify(recycleItem).slice(0, 200)}`)
      continue
    }
    if (seenRecycleItemIds.has(String(recycleItemId))) continue
    seenRecycleItemIds.add(String(recycleItemId))

    token = await refreshAdminToken()
    const permanentResp = await requestWithAdminAuthRetry(token, (activeToken) => request.post(`${BASE_URL}/api/recycle/delete-permanently`, {
      headers: { Authorization: `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
      data: { id: recycleItemId, item_type: itemType },
    }))
    const permanentBody = await permanentResp.json().catch(() => ({}))
    if (permanentResp.ok() && permanentBody.success === true) {
      permanentlyDeleted++
    } else {
      cleanupFailures.push(`permanent delete failed for recycleItemId=${recycleItemId}, originId=${originId}: status=${permanentResp.status()}, error=${permanentBody.error || JSON.stringify(permanentBody).slice(0, 200)}`)
    }
  }

  if (seenRecycleItemIds.size > 0) {
    try {
      await expect.poll(async () => {
        token = await refreshAdminToken()
        const remainingRecycleItems = await readRecycleItems(request, token)
        return remainingRecycleItems.some(item =>
          trackedFiles.some(({ fileId, fileName }) => recycleItemMatches(item, fileId, fileName))
        )
      }, {
        timeout: 10000,
        intervals: [250, 500, 1000],
      }).toBe(false)
    } catch (e) {
      cleanupFailures.push(`recycle items still visible after permanent delete: ${e.message}`)
    }
  }

  return {
    passed: cleanupFailures.length === 0,
    notes: `trackedFileIds=${trackedFiles.map(f => f.fileId).join(',') || 'none'}, softDeleted=${softDeletedFileIds.size}, alreadyInactive=${alreadyInactive}, recycleItems=${seenRecycleItemIds.size}, permanentlyDeleted=${permanentlyDeleted}, errors=${cleanupFailures.join(' | ') || 'none'}`,
  }
}
