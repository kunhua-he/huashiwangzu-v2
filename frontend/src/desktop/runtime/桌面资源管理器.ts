/**
 * 桌面按需加载 + 生命周期释放（DLR）协调器。
 * - 标记 app 活跃/空闲
 * - 调度空闲释放回调
 * - 暴露预览对象 URL 缓存
 */
import { 创建对象地址缓存, 资源缓存 } from './资源缓存'
import { 低内存策略, 探测低内存 } from './低内存'

type 释放回调 = () => void

interface 应用账本 {
  活跃窗数: number
  释放定时器: ReturnType<typeof setTimeout> | null
  释放回调: Set<释放回调>
}

const 应用账本表 = new Map<string, 应用账本>()
const 预览地址缓存 = 创建对象地址缓存()
const 通用结果缓存 = new 资源缓存<unknown>()

function 取账本(appKey: string): 应用账本 {
  let 项 = 应用账本表.get(appKey)
  if (!项) {
    项 = { 活跃窗数: 0, 释放定时器: null, 释放回调: new Set() }
    应用账本表.set(appKey, 项)
  }
  return 项
}

export function 同步缓存配额(): void {
  探测低内存()
  const 策略 = 低内存策略()
  预览地址缓存.配置({ 最大条数: 策略.预览缓存条数, 存活毫秒: 策略.预览存活毫秒 })
  通用结果缓存.配置({ 最大条数: 策略.预览缓存条数, 存活毫秒: 策略.预览存活毫秒 })
}

export function 标记应用活跃(appKey: string): void {
  if (!appKey) return
  const 项 = 取账本(appKey)
  项.活跃窗数 += 1
  if (项.释放定时器) {
    clearTimeout(项.释放定时器)
    项.释放定时器 = null
  }
}

export function 标记应用空闲(appKey: string): void {
  if (!appKey) return
  const 项 = 应用账本表.get(appKey)
  if (!项) return
  项.活跃窗数 = Math.max(0, 项.活跃窗数 - 1)
  if (项.活跃窗数 > 0) return
  调度应用释放(appKey)
}

export function 注册应用释放回调(appKey: string, 回调: 释放回调): () => void {
  const 项 = 取账本(appKey)
  项.释放回调.add(回调)
  return () => 项.释放回调.delete(回调)
}

function 调度应用释放(appKey: string): void {
  const 项 = 应用账本表.get(appKey)
  if (!项) return
  if (项.释放定时器) clearTimeout(项.释放定时器)
  const 策略 = 低内存策略()
  项.释放定时器 = setTimeout(() => {
    项.释放定时器 = null
    if (项.活跃窗数 > 0) return
    for (const cb of [...项.释放回调]) {
      try { cb() } catch { /* ignore */ }
    }
  }, 策略.窗内容空闲毫秒)
}

export function 登记预览对象地址(键: string, objectUrl: string): string {
  同步缓存配额()
  预览地址缓存.写入(键, objectUrl)
  return objectUrl
}

export function 读取预览对象地址(键: string): string | undefined {
  return 预览地址缓存.读取(键)
}

export function 释放预览对象地址(键: string): void {
  预览地址缓存.删除(键)
}

export function 写入通用缓存(键: string, 值: unknown): void {
  同步缓存配额()
  通用结果缓存.写入(键, 值)
}

export function 读取通用缓存<T>(键: string): T | undefined {
  return 通用结果缓存.读取(键) as T | undefined
}

export function 清空全部可释放缓存(): void {
  预览地址缓存.清空()
  通用结果缓存.清空()
}

export function 窗内容空闲毫秒(): number {
  return 低内存策略().窗内容空闲毫秒
}

export function 是否应冷启动内容(minimized: boolean): boolean {
  // 最小化恢复会话：默认不挂内容，点亮再加载
  return !minimized
}

export const 桌面资源管理器 = {
  同步缓存配额,
  标记应用活跃,
  标记应用空闲,
  注册应用释放回调,
  登记预览对象地址,
  读取预览对象地址,
  释放预览对象地址,
  写入通用缓存,
  读取通用缓存,
  清空全部可释放缓存,
  窗内容空闲毫秒,
  是否应冷启动内容,
}
