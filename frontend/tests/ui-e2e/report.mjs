import fs from 'fs'
import path from 'path'

import { DEFAULT_REPORT_PATH, SCREENSHOT_DIR, results } from './state.mjs'

export function generateReport() {
  const reportPath = process.env.UI_E2E_REPORT_PATH || DEFAULT_REPORT_PATH
  const reportDir = path.dirname(reportPath)
  fs.mkdirSync(reportDir, { recursive: true })

  const lines = [
    '# 前端 UI 端到端真测审核报告',
    '',
    `执行时间: ${new Date().toISOString()}`,
    `截图目录: ${SCREENSHOT_DIR}`,
    '',
    '## UI 集测矩阵',
    '',
    '| 场景 | 通过 | 截图 | 控制台 Error | 备注 |',
    '|------|------|------|-------------|------|',
  ]

  for (const result of results) {
    const screenshotLink = result.screenshot ? `[截图](${result.screenshot})` : '-'
    const consoleErrors = result.consoleErrors.length > 0 ? result.consoleErrors.slice(0, 3).join('; ') : '无'
    lines.push(`| ${result.scenario} | ${result.passed ? '✅' : '❌'} | ${screenshotLink} | ${consoleErrors} | ${result.notes || ''} |`)
  }

  lines.push('', '## 断点详情', '')
  for (const result of results.filter(item => !item.passed)) {
    lines.push(`### ${result.scenario}`)
    lines.push(`- 现象: ${result.notes || '未知'}`)
    lines.push(`- 控制台: ${result.consoleErrors.join(', ') || '无'}`)
    lines.push('')
  }

  lines.push('',
    '## 视觉清单（给小龙虾）',
    '',
    '- 本批仅验证功能性，未做视觉调整',
    '- 样式优化（配色/间距/字体）由小龙虾后续处理',
    '',
    '## 变更文件',
    '',
    '```',
    'frontend/tests/ui-e2e.spec.mjs (modified)',
    'frontend/tests/ui-e2e/*.mjs (added)',
    '```',
    '',
    '> Commit: 由当前任务提交记录为准',
    '> 未 push',
  )

  fs.writeFileSync(reportPath, lines.join('\n'), 'utf-8')
  fs.writeFileSync(path.join(reportDir, 'results.json'), JSON.stringify({ results }, null, 2), 'utf-8')
  console.log(`Report saved to ${reportPath}`)
  return reportPath
}
