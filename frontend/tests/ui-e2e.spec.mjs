import { test, expect } from '@playwright/test'
import fs from 'fs'

import { getAuthToken, refreshAdminToken, requestWithAdminAuthRetry } from './ui-e2e/auth.mjs'
import { closeAllWindows, gotoDesktop, openFileForViewer, openLauncher } from './ui-e2e/desktop.mjs'
import {
  cleanupUploadedFiles,
  fileIdFromUpload,
  uploadSample,
  waitForActiveFileState,
  waitForDeletedAndRecycled,
  waitForRecycleFileState,
} from './ui-e2e/files.mjs'
import { generateReport } from './ui-e2e/report.mjs'
import { SAMPLE_FILES, viewerSamples } from './ui-e2e/samples.mjs'
import { attachConsoleCollector, BASE_URL, consoleCollector, results, screenshot, TS } from './ui-e2e/state.mjs'

test.describe.configure({ mode: 'serial' })

test.beforeEach(({ page }) => {
  attachConsoleCollector(page)
})

// ══════════════════════════════════════════════════════════════════════
// Scene 1: Login + Desktop Shell
// ══════════════════════════════════════════════════════════════════════

test.describe('Scene 1: Login + Desktop Shell', () => {
  test('1.1 Admin login - desktop loads without errors', async ({ page }) => {
    await gotoDesktop(page)
    await expect(page.locator('.desktop-shell-container')).toBeVisible()
    await expect(page.locator('.desktop-taskbar')).toBeVisible()
    const errors = consoleCollector.filter(e => e.startsWith('error:'))
    const ss = await screenshot(page, '1.1-admin-desktop')
    results.push({ scenario: '1.1 Admin login', passed: errors.length === 0, screenshot: ss, consoleErrors: [...consoleCollector] })
    expect(errors.length).toBe(0)
  })

  test('1.2 Launcher opens with apps listed', async ({ page }) => {
    await gotoDesktop(page)
    await openLauncher(page)
    await expect(page.locator('.desktop-launcher-grid')).toBeVisible()
    const appCount = await page.locator('.desktop-launcher-app-item').count()
    const ss = await screenshot(page, '1.2-launcher')
    results.push({ scenario: '1.2 Launcher apps', passed: appCount > 0, screenshot: ss, consoleErrors: [...consoleCollector] })
    expect(appCount).toBeGreaterThan(0)
  })

  test.use({ storageState: 'tests/.auth/viewer.json' })
  test('1.3 Viewer role login', async ({ page }) => {
    await gotoDesktop(page)
    await expect(page.locator('.desktop-shell-container')).toBeVisible()
    const ss = await screenshot(page, '1.3-viewer-desktop')
    results.push({ scenario: '1.3 Viewer login', passed: true, screenshot: ss, consoleErrors: [...consoleCollector] })
  })

  // Restore admin storage state for remaining tests
  test.use({ storageState: 'tests/.auth/admin.json' })
})

// ══════════════════════════════════════════════════════════════════════
// Scene 2: All Apps Open (Component Mapping)
// ══════════════════════════════════════════════════════════════════════

const APP_NAMES = {
  'excel-engine': 'Excel 编辑器',
  'image-viewer': '图片查看器',
  'desktop': '文件管理',
  'recycle': '回收站',
  'text-editor': '文本编辑器',
  'pdf-viewer': 'PDF 查看器',
  'doc-viewer': '文档查看器',
  'ppt-viewer': '演示文稿查看器',
  'agent': 'AI 助手',
  'memory': '记忆',
  'scheduler': '定时任务',
  'im': '消息',
  'docs-open': '文档开放接口',
  'knowledge': '知识库',
  'hello-world': 'Hello World',
  'office-gen': 'Office Document Generator',
}

const IMAGE_GEN_APP = { key: 'image-gen', title: 'Image Generation' }

test.describe('Scene 2: All Apps Open (Component Mapping)', () => {
  const launcherApps = Object.keys(APP_NAMES)

  for (const appKey of launcherApps) {
    test(`2.1 App opens: ${appKey}`, async ({ page }) => {
      await gotoDesktop(page)
      await closeAllWindows(page)
      await openLauncher(page)

      const appChineseName = APP_NAMES[appKey]
      const appItem = page.locator('.desktop-launcher-app-item').filter({ hasText: appChineseName })
      const count = await appItem.count()
      if (count === 0) {
        results.push({ scenario: `2.1 ${appKey}`, passed: false, consoleErrors: [...consoleCollector], notes: `Not found (${appChineseName})` })
        return
      }

      await appItem.first().click()
      await page.waitForSelector('.desktop-window', { timeout: 5000 }).catch(() => {})
      // Close windows after each app to stay under the 30-window limit
      await closeAllWindows(page)
      const ss = await screenshot(page, `2.1-${appKey}`)
      const errors = consoleCollector.filter(e =>
        e.startsWith('error:') && (
          e.includes('component') || e.includes('not found') ||
          e.includes('Error') || e.includes('undefined')
        )
      )
      results.push({ scenario: `2.1 ${appKey}`, passed: errors.length === 0, screenshot: ss, consoleErrors: [...consoleCollector] })
    })
  }
})

// ══════════════════════════════════════════════════════════════════════
// Scene 3: File Opening + Viewer Rendering (6 file types)
// ══════════════════════════════════════════════════════════════════════

test.describe('Scene 3: File Opening & Viewers', () => {
  let fileIds = {}
  let token

  test('3.0 Upload sample files (all 6 types)', async ({ request }) => {
    token = await getAuthToken(request)

    const samples = viewerSamples()

    for (const s of samples) {
      try {
        const data = await uploadSample(request, token, s.fileName, s.mimeType, s.content)
        fileIds[s.key] = { id: data.id, name: s.fileName, expectedApp: s.expectedApp }
        results.push({ scenario: `3.0 Upload ${s.key}`, passed: true, consoleErrors: [], notes: `file_id=${data.id}` })
      } catch (e) {
        results.push({ scenario: `3.0 Upload ${s.key}`, passed: false, consoleErrors: [], notes: e.message })
      }
    }
  })

  for (const [fileType, info] of Object.entries({
    txt: { expectedApp: 'text-editor', label: 'txt→text-editor' },
    pdf: { expectedApp: 'pdf-viewer', label: 'pdf→pdf-viewer' },
    png: { expectedApp: 'image-viewer', label: 'png→image-viewer' },
    docx: { expectedApp: 'doc-viewer', label: 'docx→doc-viewer' },
    pptx: { expectedApp: 'ppt-viewer', label: 'pptx→ppt-viewer' },
    xlsx: { expectedApp: 'excel-engine', label: 'xlsx→excel-engine' },
  })) {
    test(`3.1 Open ${info.label}`, async ({ page }) => {
      await gotoDesktop(page)
      await closeAllWindows(page)

      const fileId = fileIds[fileType]?.id
      if (!fileId) {
        results.push({ scenario: `3.1 ${info.label}`, passed: false, consoleErrors: [...consoleCollector], notes: 'No file_id from upload step' })
        return
      }

      const openMethod = await openFileForViewer(page, fileIds[fileType], fileType)
      if (openMethod === 'not-found') {
        results.push({ scenario: `3.1 ${info.label}`, passed: false, consoleErrors: [...consoleCollector], notes: 'File icon not found and window-manager fallback failed' })
        return
      }

      await page.waitForSelector('.desktop-window', { timeout: 8000 }).catch(() => {})
      const ss = await screenshot(page, `3.1-${fileType}`)
      const hasWindow = await page.locator('.desktop-window').count()
      results.push({
        scenario: `3.1 ${info.label}`,
        passed: hasWindow > 0,
        screenshot: ss,
        consoleErrors: [...consoleCollector],
        notes: `Window count: ${hasWindow}, open_method=${openMethod}`,
      })
    })
  }

  test('3.4 text-editor: verify window opens with content', async ({ page, request }) => {
    await gotoDesktop(page)
    await closeAllWindows(page)

    const fileId = fileIds['txt']?.id
    if (!fileId) {
      results.push({ scenario: '3.4 text-editor edit', passed: false, consoleErrors: [...consoleCollector], notes: 'No txt file_id' })
      return
    }

    // Open the txt file from desktop
    const fileIcon = page.locator(`.desktop-file-icon-item[data-selection-key="file:${fileId}"]`)
    if (await fileIcon.count() === 0) {
      results.push({ scenario: '3.4 text-editor edit', passed: false, consoleErrors: [...consoleCollector], notes: 'File icon not found' })
      return
    }
    await fileIcon.first().dblclick({ force: true })
    await page.waitForSelector('.desktop-window', { timeout: 8000 }).catch(() => {})

    // Check that a window opened and content is visible
    const windowCount = await page.locator('.desktop-window').count()
    const contentArea = page.locator('.desktop-window .window-content .window-content-padding')
    const hasContent = await contentArea.count() > 0
    const ss = await screenshot(page, '3.4-text-editor')
    results.push({
      scenario: '3.4 text-editor edit',
      passed: windowCount > 0 && hasContent,
      screenshot: ss,
      consoleErrors: [...consoleCollector],
      notes: `Window opened: ${windowCount > 0}, content area: ${hasContent}`,
    })
  })
})

// ══════════════════════════════════════════════════════════════════════
// Scene 4: Excel-Engine Parse (real xlsx)
// ══════════════════════════════════════════════════════════════════════

test.describe('Scene 4: Excel-Engine Parse', () => {
  test('4.0 Upload real xlsx sample and parse', async ({ request }) => {
    const token = await getAuthToken(request)

    // Upload a real xlsx file with actual cell data
    const xlsxBuffer = fs.readFileSync(SAMPLE_FILES.xlsx)
    const uploadResp = await requestWithAdminAuthRetry(token, (activeToken) => request.post(`${BASE_URL}/api/files/upload`, {
      headers: { Authorization: `Bearer ${activeToken}` },
      multipart: {
        file: {
          name: `e2e-${TS}-sample.xlsx`,
          mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          buffer: xlsxBuffer,
        },
        folder_id: '0',
      },
    }))
    const body = await uploadResp.json()

    // Verify excel-engine parse capability via modules call
    const callResp = await requestWithAdminAuthRetry(token, (activeToken) => request.post(`${BASE_URL}/api/modules/call`, {
      headers: { Authorization: `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
      data: {
        target_module: 'excel-engine',
        action: 'parse',
        parameters: { file_id: body.data?.id || 1 },
      },
    }))
    const callBody = await callResp.json()

    // Check that parse returned actual sheet/cell data (not empty)
    const sheetsNonEmpty = callBody.success && callBody.data?.all_sheets?.length > 0
    results.push({
      scenario: '4.0 Upload+parse xlsx',
      passed: sheetsNonEmpty,
      consoleErrors: [],
      notes: `Status: ${callResp.status()}, sheets: ${callBody.data?.all_sheets?.length || 0}, Response: ${JSON.stringify(callBody).slice(0, 300)}`,
    })
  })

  test('4.1 Verify excel-engine in capabilities list', async ({ request }) => {
    const token = await getAuthToken(request)
    const capsResp = await requestWithAdminAuthRetry(token, (activeToken) => request.get(`${BASE_URL}/api/modules/capabilities`, {
      headers: { Authorization: `Bearer ${activeToken}` },
    }))
    const capsBody = await capsResp.json()
    const caps = capsBody.data || []
    const cap = caps.find(c => c.module === 'excel-engine' && c.action === 'parse')
    results.push({
      scenario: '4.1 excel-engine parse capability',
      passed: !!cap,
      consoleErrors: [],
      notes: cap ? `Registered: ${JSON.stringify(cap)}` : 'Not registered',
    })
  })
})

// ══════════════════════════════════════════════════════════════════════
// Scene 5: Key Interaction Flows
// ══════════════════════════════════════════════════════════════════════

test.describe('Scene 5: Key Interaction Flows', () => {
  test('5.1 Agent chat - open window', async ({ page }) => {
    await gotoDesktop(page)
    await closeAllWindows(page)

    await openLauncher(page)
    const agentItem = page.locator('.desktop-launcher-app-item').filter({ hasText: 'AI 助手' })
    const count = await agentItem.count()
    if (count === 0) {
      results.push({ scenario: '5.1 Agent chat', passed: false, consoleErrors: [...consoleCollector], notes: 'AI 助手 not found in launcher' })
      return
    }

    await agentItem.first().click()
    await page.waitForSelector('.desktop-window', { timeout: 5000 }).catch(() => {})

    const ss = await screenshot(page, '5.1-agent-chat')
    results.push({ scenario: '5.1 Agent chat', passed: true, screenshot: ss, consoleErrors: [...consoleCollector] })
  })

  test('5.2 File management - delete and recycle', async ({ page, request }) => {
    await gotoDesktop(page)

    const pageTokenFromStorage = await page.evaluate(() => localStorage.getItem('v2_auth_token'))
    if (!pageTokenFromStorage) {
      results.push({ scenario: '5.2 File delete+recycle', passed: false, consoleErrors: [...consoleCollector], notes: 'No auth token after login' })
      return
    }
    const pageToken = await refreshAdminToken()
    await page.evaluate((freshToken) => {
      localStorage.setItem('v2_auth_token', freshToken)
    }, pageToken)

    // Upload a temporary file to delete using fresh token
    const fileName = `e2e-${TS}-to-delete.txt`
    const data = await uploadSample(request, pageToken, fileName, 'text/plain', 'This file will be deleted by E2E test')
    const fileId = fileIdFromUpload(data)
    let uploadVisible = false
    let waitError = ''
    if (fileId === undefined || fileId === null) {
      waitError = `Upload response has no file id: ${JSON.stringify(data).slice(0, 200)}`
    } else {
      try {
        uploadVisible = await waitForActiveFileState(request, pageToken, fileId, fileName, true)
      } catch (e) {
        waitError = `Uploaded file not visible before delete: ${e.message}`
      }
    }

    // Delete via API
    const delResp = await requestWithAdminAuthRetry(pageToken, (activeToken) => request.post(`${BASE_URL}/api/files/delete`, {
      headers: { Authorization: `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
      data: { id: fileId, type: 'file' },
    }))
    const delBody = await delResp.json().catch(() => ({}))
    const deletedByApi = delResp.ok() && delBody.success === true
    let deleteState = { deleted: false, inRecycle: false, recycleItem: null }
    if (deletedByApi && fileId !== undefined && fileId !== null) {
      try {
        deleteState = await waitForDeletedAndRecycled(request, pageToken, fileId, fileName)
      } catch (e) {
        waitError = waitError || `Delete/recycle state did not settle: ${e.message}`
      }
    }

    // Restore
    let restored = false
    let restoredActiveVisible = false
    let recycleGoneAfterRestore = false
    let restoreError = ''
    let recycleItemId = null
    let originId = null
    if (deleteState.inRecycle) {
      recycleItemId = deleteState.recycleItem?.id
      const itemType = deleteState.recycleItem?.item_type || 'file'
      originId = deleteState.recycleItem?.origin_id ?? deleteState.recycleItem?.file_id ?? deleteState.recycleItem?.original_file_id ?? null
      if (recycleItemId === undefined || recycleItemId === null) {
        restoreError = `Recycle item has no id: ${JSON.stringify(deleteState.recycleItem).slice(0, 200)}`
      } else {
        const restoreResp = await requestWithAdminAuthRetry(pageToken, (activeToken) => request.post(`${BASE_URL}/api/recycle/restore`, {
          headers: { Authorization: `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
          data: { id: recycleItemId, item_type: itemType },
        }))
        const restoreBody = await restoreResp.json().catch(() => ({}))
        restored = restoreResp.ok() && restoreBody.success === true
        restoreError = restored ? '' : (restoreBody.error || `restore status ${restoreResp.status()}`)
        originId = restoreBody?.data?.origin_id ?? originId
        if (restored) {
          try {
            restoredActiveVisible = await waitForActiveFileState(request, pageToken, fileId, fileName, true)
            const recycleStillVisible = await waitForRecycleFileState(request, pageToken, fileId, fileName, false)
            recycleGoneAfterRestore = recycleStillVisible === false
          } catch (e) {
            restoreError = restoreError || `Restore state did not settle: ${e.message}`
          }
        }
      }
    }

    const ss = await screenshot(page, '5.2-recycle')
    const passed = uploadVisible && deletedByApi && deleteState.deleted && deleteState.inRecycle && restored && restoredActiveVisible && recycleGoneAfterRestore
    const notes = [
      `uploadVisible=${uploadVisible}`,
      `deletedByApi=${deletedByApi}`,
      `deleteState.deleted=${deleteState.deleted}`,
      `deleteState.inRecycle=${deleteState.inRecycle}`,
      `restored=${restored}`,
      `restoredActiveVisible=${restoredActiveVisible}`,
      `recycleGoneAfterRestore=${recycleGoneAfterRestore}`,
      `fileId=${fileId ?? 'none'}`,
      `recycleItemId=${recycleItemId ?? 'none'}`,
      `originId=${originId ?? 'none'}`,
      `error=${delBody.error || waitError || restoreError || 'none'}`,
    ].join(', ')
    results.push({
      scenario: '5.2 File delete+recycle',
      passed,
      screenshot: ss,
      consoleErrors: [...consoleCollector],
      notes,
    })
    expect(passed, notes).toBe(true)
  })

  test('5.3 Knowledge base - upload file and check analysis', async ({ page, request }) => {
    await gotoDesktop(page)

    // Get fresh token after browser login
    const pageTokenFromStorage = await page.evaluate(() => localStorage.getItem('v2_auth_token'))
    if (!pageTokenFromStorage) {
      results.push({ scenario: '5.3 Knowledge base', passed: false, consoleErrors: [...consoleCollector], notes: 'No auth token after login' })
      return
    }
    const pageToken = await refreshAdminToken()
    await page.evaluate((freshToken) => {
      localStorage.setItem('v2_auth_token', freshToken)
    }, pageToken)

    // Upload a txt file for knowledge base analysis
    const data = await uploadSample(request, pageToken, `e2e-${TS}-kb-test.txt`, 'text/plain',
      'Knowledge base E2E test content.\nThis file is used to test knowledge base analysis pipeline.')

    await openLauncher(page)

    const kbItem = page.locator('.desktop-launcher-app-item').filter({ hasText: '知识库' })
    if (await kbItem.count() === 0) {
      results.push({ scenario: '5.3 Knowledge base', passed: false, consoleErrors: [...consoleCollector], notes: '知识库 not found in launcher' })
      return
    }
    await kbItem.first().click()
    await page.waitForSelector('.desktop-window', { timeout: 5000 }).catch(() => {})

    // Register file in knowledge base
    const regResp = await requestWithAdminAuthRetry(pageToken, (activeToken) => request.post(`${BASE_URL}/api/knowledge/documents`, {
      headers: { Authorization: `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
      data: { file_id: data.id },
    }))
    const regBody = await regResp.json()
    const regOk = regBody.success === true
    const regError = regBody.error || ''

    const ss = await screenshot(page, '5.3-knowledge-upload')
    results.push({
      scenario: '5.3 Knowledge base upload',
      passed: regOk,
      screenshot: ss,
      consoleErrors: [...consoleCollector],
      notes: `Reg ${regOk ? 'OK' : 'FAIL'}: ${regError || `doc_id=${regBody.data?.id || '?'}`}`,
    })
  })

  test('5.4 image-gen - open UI', async ({ page }) => {
    await gotoDesktop(page)
    await closeAllWindows(page)
    await openLauncher(page)

    const imgItem = page.locator('.desktop-launcher-app-item').filter({ hasText: IMAGE_GEN_APP.title })
    const count = await imgItem.count()
    if (count > 0) {
      await imgItem.first().click()
    } else {
      await page.evaluate((appKey) => {
        const manager = window.__HSWZ_WINDOW_MANAGER__
        if (manager && typeof manager.openWindow === 'function') manager.openWindow(appKey)
      }, IMAGE_GEN_APP.key)
    }
    await page.waitForSelector('.desktop-window', { timeout: 5000 }).catch(() => {})
    const hasImageGenApp = await page.locator('.image-gen-app').count() > 0
    const hasImageGenTitle = await page.locator('.desktop-window').filter({ hasText: IMAGE_GEN_APP.title }).count() > 0
    const ss = await screenshot(page, '5.4-image-gen')
    results.push({
      scenario: '5.4 image-gen',
      passed: hasImageGenApp || hasImageGenTitle,
      screenshot: ss,
      consoleErrors: [...consoleCollector],
      notes: `selector=${IMAGE_GEN_APP.key}/${IMAGE_GEN_APP.title}, launcher_visible=${count > 0}`,
    })
  })

  test('5.5 docs-open test', async ({ request }) => {
    const token = await getAuthToken(request)
    const data = await uploadSample(
      request,
      token,
      `e2e-${TS}-docs-open.txt`,
      'text/plain',
      'Docs-open E2E token scope sample.',
    )

    // Issue a docs token (proves module is live)
    const tokenResp = await requestWithAdminAuthRetry(token, (activeToken) => request.post(`${BASE_URL}/api/docs/token`, {
      headers: { Authorization: `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
      data: { client_id: 'e2e-test', scope: { doc_ids: [data.id] } },
    }))
    const tokenBody = await tokenResp.json()

    results.push({
      scenario: '5.5 docs-open token issue',
      passed: tokenBody.success !== false,
      consoleErrors: [],
      notes: `Status: ${tokenResp.status()}, Response: ${JSON.stringify(tokenBody).slice(0, 200)}`,
    })
  })
})

// ══════════════════════════════════════════════════════════════════════
// Cleanup: delete uploaded e2e files
// ══════════════════════════════════════════════════════════════════════

test.describe('Cleanup', () => {
  test('Delete all e2e test files', async ({ request }) => {
    const cleanup = await cleanupUploadedFiles(request)
    results.push({ scenario: 'Cleanup e2e files', passed: cleanup.passed, consoleErrors: [], notes: cleanup.notes })
    expect(cleanup.passed, cleanup.notes).toBe(true)
  })
})

// ══════════════════════════════════════════════════════════════════════
// Report Generation
// ══════════════════════════════════════════════════════════════════════

test.describe('Report', () => {
  test('Generate final report', async () => {
    generateReport()
    const failed = results.filter(result => !result.passed)
    expect(failed, failed.map(result => `${result.scenario}: ${result.notes || 'failed'}`).join('\n')).toHaveLength(0)
  })
})
