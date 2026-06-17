import { onUnmounted, watch, type Ref } from 'vue'
import { API_BASE_URL } from '@/shared/api'
import type { KnowledgeTaskEntry } from '@/shared/api/types'

type RealTimeActivityItem = { time: string; file_id: number; file_name: string; status: string; current_step: string; percent: number }
type PushSnapshot = { task_list: KnowledgeTaskEntry[]; recent_logs: RealTimeActivityItem[] }
const defaultTaskProgressTabKey = 'task-progress'

export function useTaskPolling(
  activeTab: Ref<string>,
  updateSnapshot: (data: PushSnapshot) => void,
  taskProgressTabKey = defaultTaskProgressTabKey,
) {
  let sse: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let destroyed = false

  function disconnect() {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
    if (sse) { sse.close(); sse = null }
  }

  function connect() {
    if (destroyed || activeTab.value !== taskProgressTabKey) return
    disconnect()
    sse = new EventSource(`${API_BASE_URL}/knowledge/tasks/stream`)
    sse.onmessage = (e) => {
      try {
        updateSnapshot(JSON.parse(e.data) as PushSnapshot)
      } catch { /* ignore parse errors */ }
    }
    sse.onerror = () => {
      disconnect()
      if (!destroyed && activeTab.value === taskProgressTabKey) reconnectTimer = setTimeout(connect, 1500)
    }
  }

  watch(activeTab, tab => {
    if (tab === taskProgressTabKey) connect()
    else disconnect()
  }, { immediate: true })

  onUnmounted(() => { destroyed = true; disconnect() })
}
