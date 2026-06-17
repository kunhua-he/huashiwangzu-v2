import { onUnmounted } from 'vue'
import emitter from './index'
import type { DesktopEventTypes } from './event-types'

export function useDesktopEventBus() {
  const listenerEntries: Array<{ event: keyof DesktopEventTypes; handler: (...args: unknown[]) => void }> = []

  function on<T extends keyof DesktopEventTypes>(event: T, handler: (data: DesktopEventTypes[T]) => void) {
    emitter.on(event, handler)
    listenerEntries.push({ event, handler: handler as (...args: unknown[]) => void })
  }

  function off<T extends keyof DesktopEventTypes>(event: T, handler: (data: DesktopEventTypes[T]) => void) {
    emitter.off(event, handler)
    const index = listenerEntries.findIndex(item => item.event === event && item.handler === handler)
    if (index > -1) listenerEntries.splice(index, 1)
  }

  function emit<T extends keyof DesktopEventTypes>(event: T, data: DesktopEventTypes[T]) {
    emitter.emit(event, data)
  }

  onUnmounted(() => {
    listenerEntries.forEach(({ event, handler }) => {
      emitter.off(event, handler)
    })
  })

  return { on, off, emit }
}
