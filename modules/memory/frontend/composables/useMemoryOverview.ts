import { computed } from 'vue'
import type { MemoryOverviewCopy } from '../types'

export function useMemoryOverview() {
  const copy = computed<MemoryOverviewCopy>(() => ({
    title: '记忆',
    description: '通过 Agent 对话记事和回忆',
    hint: '打开 Agent，说「记住…」或「我之前说过…」即可使用',
  }))

  return { copy }
}
