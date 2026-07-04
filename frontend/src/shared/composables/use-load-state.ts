import { ref, type Ref } from 'vue'
import { toApiErrorInfo, type ApiErrorInfo } from '@/shared/api/response-transform'

export type LoadStatus = 'idle' | 'loading' | 'ready' | 'error' | 'stale'

export interface LoadState<T> {
  status: LoadStatus
  data: T
  error: ApiErrorInfo | null
  lastLoadedAt?: string
}

export function createLoadState<T>(data: T): Ref<LoadState<T>> {
  return ref({
    status: 'idle',
    data,
    error: null,
  }) as Ref<LoadState<T>>
}

export function startLoading<T>(state: Ref<LoadState<T>>): void {
  state.value = {
    ...state.value,
    status: 'loading',
    error: null,
  }
}

export function finishLoading<T>(state: Ref<LoadState<T>>, data: T): void {
  state.value = {
    status: 'ready',
    data,
    error: null,
    lastLoadedAt: new Date().toISOString(),
  }
}

export function failLoading<T>(state: Ref<LoadState<T>>, error: unknown, fallbackMessage: string): ApiErrorInfo {
  const info = toApiErrorInfo(error, fallbackMessage)
  state.value = {
    ...state.value,
    status: state.value.lastLoadedAt ? 'stale' : 'error',
    error: info,
  }
  return info
}
