import { onUnmounted, watch, type Ref } from 'vue'
import { API_BASE_URL } from '@/shared/api'
import type { KnowledgeTaskEntry } from '@/shared/api/types'

type RealTimeActivityItem = { time: string; file_id: number; file_name: string; status: string; current_step: string; percent: number }
type PushSnapshot = { task_list: KnowledgeTaskEntry[]; recent_logs: RealTimeActivityItem[] }

export function use任务轮询(
  激活标签: Ref<string>,
  更新快照: (数据: PushSnapshot) => void,
) {
  let sse: EventSource | null = null
  let 重连定时器: ReturnType<typeof setTimeout> | null = null
  let 已销毁 = false

  function 断开() {
    if (重连定时器) { clearTimeout(重连定时器); 重连定时器 = null }
    if (sse) { sse.close(); sse = null }
  }

  function 连接() {
    if (已销毁 || 激活标签.value !== '任务进度') return
    断开()
    sse = new EventSource(`${API_BASE_URL}/knowledge/tasks/stream`)
    sse.onmessage = (e) => {
      try {
        更新快照(JSON.parse(e.data) as PushSnapshot)
      } catch { /* ignore parse errors */ }
    }
    sse.onerror = () => {
      断开()
      if (!已销毁 && 激活标签.value === '任务进度') 重连定时器 = setTimeout(连接, 1500)
    }
  }

  watch(激活标签, 标签 => {
    if (标签 === '任务进度') 连接()
    else 断开()
  }, { immediate: true })

  onUnmounted(() => { 已销毁 = true; 断开() })
}
