let ghostEl: HTMLElement | null = null
let ghostOffsets = { x: 16, y: 16 }

function getPrimaryEl(key: string): HTMLElement | null {
  return document.querySelector(`[data-selection-key="${key}"]`) as HTMLElement | null
}

function buildGhost(ids: string[]): HTMLElement {
  const ghost = document.createElement('div')
  ghost.id = 'drag-ghost-el'
  ghost.style.cssText =
    'position:fixed;z-index:2147483647;pointer-events:none;opacity:0.92;transition:none;'

  const inner = document.createElement('div')
  inner.style.cssText =
    'display:flex;align-items:center;gap:8px;padding:6px 12px;' +
    'background:rgba(255,255,255,0.96);border-radius:8px;' +
    'box-shadow:0 4px 20px rgba(15,23,42,0.18);border:1px solid #c8d4e4;'

  const primaryEl = getPrimaryEl(ids[0])
  if (primaryEl) {
    const iconEl =
      primaryEl.querySelector('.desktop-icon-image, .file-visual-icon-wrapper, .file-entry-icon') ||
      primaryEl.querySelector('svg, img')
    if (iconEl) {
      const cloned = iconEl.cloneNode(true) as HTMLElement
      cloned.style.cssText = 'width:32px;height:32px;flex-shrink:0;'
      inner.appendChild(cloned)
    } else {
      const fb = document.createElement('span')
      fb.textContent = '📄'
      fb.style.cssText = 'font-size:24px;line-height:1;'
      inner.appendChild(fb)
    }

    const label = document.createElement('span')
    label.textContent =
      primaryEl.querySelector('.desktop-icon-label, .fm-entry-name')?.textContent || '项'
    label.style.cssText =
      'font-size:13px;color:#1e293b;white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis;'
    inner.appendChild(label)
  }

  if (ids.length > 1) {
    const badge = document.createElement('span')
    badge.textContent = `${ids.length}项`
    badge.style.cssText =
      'font-size:11px;color:#475569;background:#f1f5f9;border-radius:10px;padding:1px 7px;flex-shrink:0;'
    inner.appendChild(badge)
  }

  ghost.appendChild(inner)
  return ghost
}

export function createDragGhost(ids: string[], x: number, y: number): void {
  removeDragGhost()
  ghostEl = buildGhost(ids)
  ghostEl.style.left = `${x + ghostOffsets.x}px`
  ghostEl.style.top = `${y + ghostOffsets.y}px`
  document.body.appendChild(ghostEl)
}

export function updateDragGhostPosition(x: number, y: number): void {
  if (!ghostEl) return
  ghostEl.style.left = `${x + ghostOffsets.x}px`
  ghostEl.style.top = `${y + ghostOffsets.y}px`
}

export function removeDragGhost(): void {
  if (ghostEl) {
    ghostEl.remove()
    ghostEl = null
  }
}
