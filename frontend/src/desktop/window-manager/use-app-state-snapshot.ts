import { ref, watch, type Ref } from 'vue'
import { desktopStateStore, readAppState, updateAppState } from './desktop-state-store'

export function useAppStateSnapshot<T>(appId: string, stateName: string, defaultValue: T, validator?: (value: T) => boolean): Ref<T> {
  const state = ref<T>(defaultValue) as Ref<T>
  let loaded = false

  function read() {
    loaded = false
    const value = readAppState(appId, stateName, defaultValue)
    if (!validator || validator(value)) state.value = value
    loaded = true
  }

  watch(desktopStateStore.loaded, (ready: boolean) => { if (ready) read() }, { immediate: true })
  watch(state, (value: T) => {
    if (!loaded) return
    updateAppState(appId, stateName, value)
  }, { deep: true })

  return state
}
