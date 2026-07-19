/**
 * 通用 LRU + TTL 缓存。
 * 用于缩略图 blob、Quick Look 缓冲、Spotlight 结果等可释放资源。
 */
export type 缓存释放器<V> = (value: V, key: string) => void

export interface 缓存选项<V> {
  最大条数?: number
  存活毫秒?: number
  释放?: 缓存释放器<V>
}

interface 缓存条目<V> {
  值: V
  过期于: number
  最近访问: number
}

export class 资源缓存<V> {
  private 表 = new Map<string, 缓存条目<V>>()
  private 最大条数: number
  private 存活毫秒: number
  private 释放?: 缓存释放器<V>

  constructor(选项: 缓存选项<V> = {}) {
    this.最大条数 = Math.max(1, 选项.最大条数 ?? 80)
    this.存活毫秒 = Math.max(1_000, 选项.存活毫秒 ?? 180_000)
    this.释放 = 选项.释放
  }

  配置(选项: 缓存选项<V>): void {
    if (选项.最大条数 !== undefined) this.最大条数 = Math.max(1, 选项.最大条数)
    if (选项.存活毫秒 !== undefined) this.存活毫秒 = Math.max(1_000, 选项.存活毫秒)
    if (选项.释放) this.释放 = 选项.释放
    this.清理过期()
    this.裁剪到上限()
  }

  读取(键: string): V | undefined {
    const 条目 = this.表.get(键)
    if (!条目) return undefined
    if (条目.过期于 <= Date.now()) {
      this.删除(键)
      return undefined
    }
    条目.最近访问 = Date.now()
    // Map 保持插入序：重插以抬升 LRU
    this.表.delete(键)
    this.表.set(键, 条目)
    return 条目.值
  }

  写入(键: string, 值: V): void {
    const 旧 = this.表.get(键)
    if (旧) this.安全释放(旧.值, 键)
    this.表.set(键, {
      值,
      过期于: Date.now() + this.存活毫秒,
      最近访问: Date.now(),
    })
    this.裁剪到上限()
  }

  触碰(键: string): void {
    this.读取(键)
  }

  删除(键: string): void {
    const 条目 = this.表.get(键)
    if (!条目) return
    this.表.delete(键)
    this.安全释放(条目.值, 键)
  }

  清空(): void {
    for (const [键, 条目] of this.表) this.安全释放(条目.值, 键)
    this.表.clear()
  }

  get 大小(): number {
    return this.表.size
  }

  清理过期(): number {
    const 现在 = Date.now()
    let 数 = 0
    for (const [键, 条目] of this.表) {
      if (条目.过期于 <= 现在) {
        this.删除(键)
        数 += 1
      }
    }
    return 数
  }

  private 裁剪到上限(): void {
    while (this.表.size > this.最大条数) {
      const 最旧 = this.表.keys().next().value as string | undefined
      if (!最旧) break
      this.删除(最旧)
    }
  }

  private 安全释放(值: V, 键: string): void {
    try {
      this.释放?.(值, 键)
    } catch {
      /* 释放失败不影响主流程 */
    }
  }
}

/** 对象 URL 专用缓存：淘汰时自动 revokeObjectURL */
export function 创建对象地址缓存(选项: Omit<缓存选项<string>, '释放'> = {}) {
  return new 资源缓存<string>({
    ...选项,
    释放: (url) => {
      try { URL.revokeObjectURL(url) } catch { /* ignore */ }
    },
  })
}
