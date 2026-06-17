import { onUnmounted } from 'vue'
import emitter from './index'
import type { DesktopEventTypes } from './event-types'

interface ListenerRecord {
  event: string
  handler: (payload: unknown) => void
}

export function useAppEventBus() {
  const listenerEntries: ListenerRecord[] = []

  function on<T extends keyof DesktopEventTypes>(event: T, handler: (data: DesktopEventTypes[T]) => void) {
    emitter.on(event, handler as never)
    listenerEntries.push({ event: event as string, handler: handler as unknown as (payload: unknown) => void })
  }

  function off<T extends keyof DesktopEventTypes>(event: T, handler: (data: DesktopEventTypes[T]) => void) {
    emitter.off(event, handler as never)
    const index = listenerEntries.findIndex(item => item.event === event && item.handler === handler)
    if (index > -1) listenerEntries.splice(index, 1)
  }

  function emit<T extends keyof DesktopEventTypes>(event: T, data: DesktopEventTypes[T]) {
    emitter.emit(event, data)
  }

  function once<T extends keyof DesktopEventTypes>(event: T, handler: (data: DesktopEventTypes[T]) => void) {
    const wrappedHandler = (data: DesktopEventTypes[T]) => {
      handler(data)
      off(event, wrappedHandler)
    }
    on(event, wrappedHandler)
  }

  onUnmounted(() => {
    listenerEntries.forEach(({ event, handler }) => {
      emitter.off(event as never, handler as never)
    })
  })

  return { on, off, emit, once }
}
