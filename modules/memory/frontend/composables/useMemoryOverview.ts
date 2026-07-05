import { computed, onMounted, ref } from 'vue'
import { deleteMemory, listMemories, recallMemories } from '../api'
import type { MemoryListResult, MemoryRecord, MemorySearchMode } from '../types'

const PAGE_SIZE = 50

export function useMemoryOverview() {
  const memories = ref<MemoryRecord[]>([])
  const selectedId = ref<number | null>(null)
  const query = ref('')
  const mode = ref<MemorySearchMode>('semantic')
  const loading = ref(false)
  const searching = ref(false)
  const deletingId = ref<number | null>(null)
  const error = ref('')
  const notice = ref('')
  const hasLoaded = ref(false)

  const filteredMemories = computed(() => {
    if (mode.value !== 'keyword') return memories.value
    const term = query.value.trim().toLowerCase()
    if (!term) return memories.value
    return memories.value.filter(item => searchableText(item).includes(term))
  })
  const selectedMemory = computed(() => (
    filteredMemories.value.find(item => item.id === selectedId.value) ?? filteredMemories.value[0] ?? null
  ))
  const totalLabel = computed(() => {
    const count = filteredMemories.value.length
    if (searching.value) return '检索中'
    if (loading.value) return '加载中'
    return count ? `${count} 条记忆` : '暂无记忆'
  })
  const emptyMessage = computed(() => {
    if (!hasLoaded.value || loading.value || searching.value) return '正在读取记忆'
    if (query.value.trim()) return '没有匹配的记忆；换个关键词，或回到 Agent 里产生新的记忆。'
    return '暂无记忆；需要先在 Agent 中对话并产生可保存的事实、偏好或经验。'
  })

  onMounted(() => {
    void refresh()
  })

  async function refresh() {
    loading.value = true
    error.value = ''
    notice.value = ''
    try {
      const payload = await listMemories(PAGE_SIZE, 0)
      memories.value = normalizeList(payload)
      keepSelection()
    } catch (caught: unknown) {
      error.value = readableError(caught)
      memories.value = []
      selectedId.value = null
    } finally {
      loading.value = false
      hasLoaded.value = true
    }
  }

  async function search() {
    const term = query.value.trim()
    if (!term) {
      await refresh()
      return
    }
    searching.value = true
    error.value = ''
    notice.value = ''
    try {
      if (mode.value === 'semantic') {
        memories.value = await recallMemories(term, 20)
      } else {
        const payload = await listMemories(PAGE_SIZE, 0)
        memories.value = normalizeList(payload).filter(item => searchableText(item).includes(term.toLowerCase()))
      }
      keepSelection()
    } catch (caught: unknown) {
      error.value = readableError(caught)
    } finally {
      searching.value = false
      hasLoaded.value = true
    }
  }

  async function removeSelected() {
    const memory = selectedMemory.value
    if (!memory) return
    const confirmed = window.confirm(`删除记忆 #${memory.id}？此操作会从当前用户记忆中移除它。`)
    if (!confirmed) return
    deletingId.value = memory.id
    error.value = ''
    notice.value = ''
    try {
      await deleteMemory(memory.id)
      memories.value = memories.value.filter(item => item.id !== memory.id)
      selectedId.value = memories.value[0]?.id ?? null
      notice.value = `已删除记忆 #${memory.id}`
    } catch (caught: unknown) {
      error.value = readableError(caught)
    } finally {
      deletingId.value = null
    }
  }

  function selectMemory(id: number) {
    selectedId.value = id
  }

  function clearSearch() {
    query.value = ''
    void refresh()
  }

  function setMode(nextMode: MemorySearchMode) {
    mode.value = nextMode
    if (query.value.trim()) void search()
  }

  function keepSelection() {
    if (selectedId.value && memories.value.some(item => item.id === selectedId.value)) return
    selectedId.value = memories.value[0]?.id ?? null
  }

  return {
    memories,
    filteredMemories,
    selectedId,
    selectedMemory,
    query,
    mode,
    loading,
    searching,
    deletingId,
    error,
    notice,
    totalLabel,
    emptyMessage,
    refresh,
    search,
    clearSearch,
    removeSelected,
    selectMemory,
    setMode,
  }
}

function normalizeList(payload: MemoryListResult): MemoryRecord[] {
  return Array.isArray(payload) ? payload : payload.items ?? []
}

function searchableText(item: MemoryRecord): string {
  return [
    item.text,
    item.summary,
    item.tags,
    item.keywords,
    item.source,
    item.memory_type,
    item.conversation_id === null ? '' : String(item.conversation_id),
  ].filter((part): part is string => Boolean(part)).join('\n').toLowerCase()
}

function readableError(caught: unknown): string {
  return caught instanceof Error ? caught.message : String(caught || '加载失败')
}
