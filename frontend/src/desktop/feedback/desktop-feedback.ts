/**
 * 桌面反馈系统 - 微动画 + 操作提示
 *
 * 设计原则：
 * 1. 用户每个操作都有即时视觉响应
 * 2. 轻量，不阻塞主逻辑
 * 3. 可通过 desktopConfig.enableMicroAnimations 全局开关
 */
import { ref } from 'vue'
import { desktopConfig } from '@/desktop/config/desktop-preferences'

// ═══════════════════════════════════════════════════
// 微动画
// ═══════════════════════════════════════════════════

/**
 * 给元素添加一次性弹跳动画
 * 用途：点击图标时、操作成功时
 */
export function animateBounce(el: HTMLElement | null, scale = 0.92): void {
  if (!el || !desktopConfig.enableMicroAnimations) return
  el.style.transition = 'transform 120ms cubic-bezier(0.34, 1.56, 0.64, 1)'
  el.style.transform = `scale(${scale})`
  requestAnimationFrame(() => {
    setTimeout(() => {
      el.style.transform = ''
      setTimeout(() => { el.style.transition = '' }, 150)
    }, 100)
  })
}

/**
 * 脉冲动画（放大再缩回）
 * 用途：收到通知时、有新内容时
 */
export function animatePulse(el: HTMLElement | null): void {
  if (!el || !desktopConfig.enableMicroAnimations) return
  el.style.transition = 'transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1)'
  el.style.transform = 'scale(1.08)'
  setTimeout(() => {
    el.style.transform = ''
    setTimeout(() => { el.style.transition = '' }, 220)
  }, 200)
}

/**
 * 涟漪效果（在鼠标点击处产生扩散圈）
 * 用途：桌面空白区域点击
 */
export function createRipple(container: HTMLElement, x: number, y: number): void {
  if (!desktopConfig.enableMicroAnimations) return
  const ripple = document.createElement('div')
  ripple.className = 'desktop-feedback-ripple'
  const rect = container.getBoundingClientRect()
  ripple.style.left = `${x - rect.left}px`
  ripple.style.top = `${y - rect.top}px`
  container.appendChild(ripple)
  setTimeout(() => ripple.remove(), 500)
}

/**
 * 闪烁高亮（元素短暂变亮）
 * 用途：粘贴成功时目标区域闪一下
 */
export function animateFlash(el: HTMLElement | null): void {
  if (!el || !desktopConfig.enableMicroAnimations) return
  el.style.transition = 'box-shadow 150ms ease'
  el.style.boxShadow = '0 0 0 2px rgba(59, 130, 246, 0.5), 0 0 12px rgba(59, 130, 246, 0.3)'
  setTimeout(() => {
    el.style.boxShadow = ''
    setTimeout(() => { el.style.transition = '' }, 180)
  }, 300)
}

// ═══════════════════════════════════════════════════
// 操作轻提示（右下角快速消息）
// ═══════════════════════════════════════════════════

export interface OperationToast {
  id: number
  message: string
  icon: string
  type: 'success' | 'info' | 'warning' | 'error'
  duration: number
}

const toastCounter = { value: 0 }
export const activeToasts = ref<OperationToast[]>([])

export function showToast(
  message: string,
  options: { icon?: string; type?: OperationToast['type']; duration?: number } = {}
): void {
  if (!desktopConfig.enableOperationToast) return
  const toast: OperationToast = {
    id: ++toastCounter.value,
    message,
    icon: options.icon || getDefaultIcon(options.type || 'success'),
    type: options.type || 'success',
    duration: options.duration || 2500,
  }
  activeToasts.value.push(toast)
  if (activeToasts.value.length > 5) {
    activeToasts.value.shift()
  }
  setTimeout(() => {
    const idx = activeToasts.value.findIndex(t => t.id === toast.id)
    if (idx !== -1) activeToasts.value.splice(idx, 1)
  }, toast.duration)
}

/** Element Plus 兼容别名，方便桌面路径逐步去 Element 化 */
export const desktopMessage = {
  success(message: string) { showToast(message, { type: 'success' }) },
  info(message: string) { showToast(message, { type: 'info' }) },
  warning(message: string) { showToast(message, { type: 'warning' }) },
  error(message: string) { showToast(message, { type: 'error' }) },
}

export type DesktopDialogMode = 'alert' | 'confirm' | 'prompt'
export type DesktopDialogChoice = 'confirm' | 'cancel' | 'dismiss'

export interface DesktopDialogRequest {
  title: string
  message: string
  mode?: DesktopDialogMode
  confirmText?: string
  cancelText?: string
  tone?: OperationToast['type']
  defaultValue?: string
  placeholder?: string
}

export interface DesktopDialogState {
  id: number
  title: string
  message: string
  mode: DesktopDialogMode
  confirmText: string
  cancelText: string
  tone: OperationToast['type']
  inputValue: string
  placeholder: string
  resolve: (choice: DesktopDialogChoice, value?: string) => void
}

const dialogCounter = { value: 0 }
export const activeDialog = ref<DesktopDialogState | null>(null)

function openDialog(request: DesktopDialogRequest): Promise<{ choice: DesktopDialogChoice; value: string }> {
  if (activeDialog.value) activeDialog.value.resolve('dismiss')
  return new Promise((resolve) => {
    activeDialog.value = {
      id: ++dialogCounter.value,
      title: request.title,
      message: request.message,
      mode: request.mode || 'alert',
      confirmText: request.confirmText || '好',
      cancelText: request.cancelText || '取消',
      tone: request.tone || 'info',
      inputValue: request.defaultValue || '',
      placeholder: request.placeholder || '',
      resolve(choice, value = '') {
        resolve({ choice, value })
      },
    }
  })
}

export function showAlert(message: string, title = '提示'): Promise<void> {
  return openDialog({ title, message, mode: 'alert', confirmText: '好' }).then(() => undefined)
}

/** true = 确定；false = 取消或关闭 */
export function showConfirm(
  message: string,
  title = '确认',
  options: { confirmText?: string; cancelText?: string; tone?: OperationToast['type'] } = {},
): Promise<boolean> {
  return openDialog({
    title,
    message,
    mode: 'confirm',
    confirmText: options.confirmText || '确定',
    cancelText: options.cancelText || '取消',
    tone: options.tone || 'warning',
  }).then(({ choice }) => choice === 'confirm')
}

/**
 * 三路确认：confirm / cancel(点取消按钮) / dismiss(点遮罩或关闭语义)
 * 用于「替换 vs 保留两者 vs 放弃」这类冲突对话框。
 */
export function showConfirmDetailed(
  message: string,
  title = '确认',
  options: { confirmText?: string; cancelText?: string; tone?: OperationToast['type'] } = {},
): Promise<DesktopDialogChoice> {
  return openDialog({
    title,
    message,
    mode: 'confirm',
    confirmText: options.confirmText || '确定',
    cancelText: options.cancelText || '取消',
    tone: options.tone || 'warning',
  }).then(({ choice }) => choice)
}

/** 输入框对话框；确定返回字符串，取消/关闭返回 null */
export function showPrompt(
  message: string,
  title = '输入',
  options: {
    defaultValue?: string
    confirmText?: string
    cancelText?: string
    placeholder?: string
    tone?: OperationToast['type']
  } = {},
): Promise<string | null> {
  return openDialog({
    title,
    message,
    mode: 'prompt',
    confirmText: options.confirmText || '确定',
    cancelText: options.cancelText || '取消',
    tone: options.tone || 'info',
    defaultValue: options.defaultValue || '',
    placeholder: options.placeholder || '',
  }).then(({ choice, value }) => (choice === 'confirm' ? value : null))
}

export function resolveDialog(choice: DesktopDialogChoice, value?: string): void {
  const current = activeDialog.value
  if (!current) return
  const input = value !== undefined ? value : current.inputValue
  activeDialog.value = null
  current.resolve(choice, input)
}

export function updateDialogInput(value: string): void {
  if (!activeDialog.value) return
  activeDialog.value.inputValue = value
}

function getDefaultIcon(type: OperationToast['type']): string {
  switch (type) {
    case 'success': return '✓'
    case 'info': return 'ℹ'
    case 'warning': return '⚠'
    case 'error': return '✕'
  }
}

// ═══════════════════════════════════════════════════
// 进度事件总线（任务栏进度条数据源）
// ═══════════════════════════════════════════════════

export interface ProgressEntry {
  appKey: string
  progress: number  // 0~1，-1表示不确定进度（旋转动画）
  color?: string
}

export const activeProgress = ref<Map<string, ProgressEntry>>(new Map())

/** 设置应用进度（任务栏按钮底部显示进度条） */
export function setProgress(appKey: string, progress: number, color?: string): void {
  if (progress >= 1 || progress < 0) {
    activeProgress.value.delete(appKey)
  } else {
    activeProgress.value.set(appKey, { appKey, progress, color })
  }
  // 触发响应式更新
  activeProgress.value = new Map(activeProgress.value)
}

/** 清除进度 */
export function clearProgress(appKey: string): void {
  activeProgress.value.delete(appKey)
  activeProgress.value = new Map(activeProgress.value)
}
