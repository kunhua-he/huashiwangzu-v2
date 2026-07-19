/**
 * 低内存探测与降级开关。
 * 4G 机器 / 系统省电动效偏好 → 自动进入低内存策略。
 */
import { computed, reactive } from 'vue'
import { desktopConfig, type DesktopConfig } from '@/desktop/config/desktop-preferences'

export type 低内存模式 = 'auto' | 'on' | 'off'

export interface 低内存探测结果 {
  设备内存GB: number | null
  偏好减弱动效: boolean
  堆使用MB: number | null
  建议低内存: boolean
}

const 状态 = reactive({
  探测: null as 低内存探测结果 | null,
  上次探测于: 0,
})

function 读取设备内存GB(): number | null {
  const nav = navigator as Navigator & { deviceMemory?: number }
  const v = nav.deviceMemory
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

function 读取堆使用MB(): number | null {
  const perf = performance as Performance & { memory?: { usedJSHeapSize?: number } }
  const used = perf.memory?.usedJSHeapSize
  return typeof used === 'number' && Number.isFinite(used) ? Math.round(used / (1024 * 1024)) : null
}

export function 探测低内存(): 低内存探测结果 {
  const 设备内存GB = 读取设备内存GB()
  const 偏好减弱动效 = typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const 堆使用MB = 读取堆使用MB()
  const 建议低内存 = (设备内存GB !== null && 设备内存GB <= 4)
    || 偏好减弱动效
    || (堆使用MB !== null && 堆使用MB >= 900)
  const 结果: 低内存探测结果 = { 设备内存GB, 偏好减弱动效, 堆使用MB, 建议低内存 }
  状态.探测 = 结果
  状态.上次探测于 = Date.now()
  return 结果
}

export function 是否低内存生效(配置: Pick<DesktopConfig, 'lowMemoryMode'> = desktopConfig): boolean {
  const 模式 = 配置.lowMemoryMode || 'auto'
  if (模式 === 'on') return true
  if (模式 === 'off') return false
  const 探测 = 状态.探测 && (Date.now() - 状态.上次探测于 < 30_000)
    ? 状态.探测
    : 探测低内存()
  return 探测.建议低内存
}

export const 低内存生效 = computed(() => 是否低内存生效(desktopConfig))

export function 低内存策略() {
  const 低 = 是否低内存生效()
  return {
    低内存: 低,
    窗内容空闲毫秒: 低 ? 15_000 : (desktopConfig.windowContentIdleTtlMs || 45_000),
    最大暖窗数: 低 ? 3 : 8,
    预览缓存条数: 低 ? 24 : 80,
    预览存活毫秒: 低 ? 120_000 : 300_000,
    启用重玻璃: 低 ? false : desktopConfig.enableHeavyGlass !== false,
    启用微动效: 低 ? false : desktopConfig.enableMicroAnimations !== false,
    调度中心用占位卡: 低,
  }
}

export function 应用低内存样式到根(host?: HTMLElement | null): void {
  const el = host || (typeof document !== 'undefined' ? document.documentElement : null)
  if (!el) return
  const 策略 = 低内存策略()
  el.classList.toggle('desktop-low-memory', 策略.低内存)
  el.classList.toggle('desktop-heavy-glass-off', !策略.启用重玻璃)
  el.classList.toggle('desktop-micro-off', !策略.启用微动效)
}

export const 低内存状态 = 状态
