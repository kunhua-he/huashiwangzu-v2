/**
 * Excel Engine - Address utility (frontend)
 * 1:1 from old 界面/Excel预览器工具.ts
 */

/** Column number to letter: 0->A, 25->Z, 26->AA */
export function colLetter(n: number): string {
  let result = ''
  let t = n
  while (t >= 0) {
    result = String.fromCharCode((t % 26) + 65) + result
    t = Math.floor(t / 26) - 1
  }
  return result
}

/** Parse 'A1' -> { col:0, row:0 }, 'AA2' -> { col:26, row:1 } */
export function parseCellAddr(cell: string): { col: number; row: number } {
  const m = cell.match(/^([A-Z]+)(\d+)$/)
  if (!m) return { col: 0, row: 0 }
  let col = 0
  for (let i = 0; i < m[1].length; i++) {
    col = col * 26 + (m[1].charCodeAt(i) - 64)
  }
  return { col: col - 1, row: parseInt(m[2], 10) - 1 }
}

/** Build merged cell map */
export function buildMergeMap(
  mergedCells: string[]
): Map<string, { rowspan: number; colspan: number; isMain: boolean }> {
  const map = new Map<string, { rowspan: number; colspan: number; isMain: boolean }>()
  for (const range of mergedCells) {
    const [start, end] = range.split(':')
    if (!start || !end) continue
    const sp = parseCellAddr(start)
    const ep = parseCellAddr(end)
    const colspan = ep.col - sp.col + 1
    const rowspan = ep.row - sp.row + 1
    for (let r = sp.row; r <= ep.row; r++) {
      for (let c = sp.col; c <= ep.col; c++) {
        map.set(`${r}:${c}`, {
          rowspan: r === sp.row ? rowspan : 0,
          colspan: c === sp.col ? colspan : 0,
          isMain: r === sp.row && c === sp.col,
        })
      }
    }
  }
  return map
}

/** Limit display value length */
export function truncateValue(value: any, maxLen = 100): string {
  if (value === null || value === undefined) return ''
  const str = String(value)
  return str.length <= maxLen ? str : str.slice(0, maxLen) + '…'
}

/** Estimate JSON data size in MB */
export function estimateDataSizeMB(obj: any): number {
  try {
    return JSON.stringify(obj).length / (1024 * 1024)
  } catch {
    return 0
  }
}

/** Decode ASCII escape sequences */
export function decodeAsciiEscape(val: string): string {
  return val.replace(/\[ASCII:0x([0-9A-F]{4})\]/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
}
