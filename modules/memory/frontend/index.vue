<template>
  <section class="memory-app">
    <header class="memory-toolbar">
      <div class="memory-title">
        <h2>记忆</h2>
        <span>{{ totalLabel }}</span>
      </div>

      <form class="memory-search" @submit.prevent="search">
        <div class="memory-mode" role="tablist" aria-label="memory search mode">
          <button
            type="button"
            :class="{ active: mode === 'semantic' }"
            @click="setMode('semantic')"
          >
            语义
          </button>
          <button
            type="button"
            :class="{ active: mode === 'keyword' }"
            @click="setMode('keyword')"
          >
            关键词
          </button>
        </div>
        <input v-model="query" type="search" placeholder="搜索记忆、来源或标签" />
        <button type="submit" :disabled="searching">{{ searching ? '检索中' : '搜索' }}</button>
        <button type="button" :disabled="loading || searching" @click="refresh">刷新</button>
        <button v-if="query" type="button" @click="clearSearch">清空</button>
      </form>
    </header>

    <div v-if="error" class="memory-message memory-message--error">{{ error }}</div>
    <div v-if="notice" class="memory-message">{{ notice }}</div>

    <main class="memory-body">
      <aside class="memory-list" aria-label="memory list">
        <div v-if="loading && filteredMemories.length === 0" class="memory-empty">加载中...</div>
        <div v-else-if="filteredMemories.length === 0" class="memory-empty">{{ emptyMessage }}</div>

        <button
          v-for="memory in filteredMemories"
          :key="memory.id"
          type="button"
          class="memory-row"
          :class="{ active: selectedMemory?.id === memory.id }"
          @click="selectMemory(memory.id)"
        >
          <span class="memory-row__summary">{{ memory.summary || memory.text }}</span>
          <span class="memory-row__meta">
            <span>#{{ memory.id }}</span>
            <span>{{ displayType(memory.memory_type) }}</span>
            <span>{{ formatDate(memory.created_at) }}</span>
          </span>
        </button>
      </aside>

      <article v-if="selectedMemory" class="memory-detail">
        <div class="memory-detail__header">
          <div>
            <span class="memory-detail__eyebrow">Memory #{{ selectedMemory.id }}</span>
            <h3>{{ selectedMemory.summary || '未生成摘要' }}</h3>
          </div>
          <button
            type="button"
            class="memory-delete"
            :disabled="deletingId === selectedMemory.id"
            @click="removeSelected"
          >
            {{ deletingId === selectedMemory.id ? '删除中' : '删除' }}
          </button>
        </div>

        <div class="memory-metrics">
          <div>
            <span>类型</span>
            <strong>{{ displayType(selectedMemory.memory_type) }}</strong>
          </div>
          <div>
            <span>来源</span>
            <strong>{{ displaySource(selectedMemory.source) }}</strong>
          </div>
          <div>
            <span>可信度</span>
            <strong>{{ formatPercent(selectedMemory.confidence) }}</strong>
          </div>
          <div>
            <span>时间</span>
            <strong>{{ formatDateTime(selectedMemory.created_at) }}</strong>
          </div>
        </div>

        <section class="memory-section">
          <h4>正文</h4>
          <p>{{ selectedMemory.text }}</p>
        </section>

        <section class="memory-section">
          <h4>来源与检索线索</h4>
          <dl class="memory-fields">
            <div>
              <dt>标签</dt>
              <dd>{{ selectedMemory.tags || '暂无标签' }}</dd>
            </div>
            <div>
              <dt>关键词</dt>
              <dd>{{ selectedMemory.keywords || '暂无关键词' }}</dd>
            </div>
            <div>
              <dt>会话</dt>
              <dd>{{ selectedMemory.conversation_id ?? '无会话关联' }}</dd>
            </div>
            <div v-if="selectedMemory.similarity !== undefined">
              <dt>相似度</dt>
              <dd>{{ formatPercent(selectedMemory.similarity) }}</dd>
            </div>
            <div>
              <dt>新近度</dt>
              <dd>{{ formatPercent(selectedMemory.recency_score) }}</dd>
            </div>
            <div>
              <dt>访问</dt>
              <dd>{{ selectedMemory.access_count ?? 0 }} 次</dd>
            </div>
          </dl>
        </section>
      </article>

      <section v-else class="memory-detail memory-detail--empty">
        <h3>暂无记忆详情</h3>
        <p>需要先在 Agent 中产生记忆；保存后这里会显示类型、来源、时间、可信度和可检索内容。</p>
      </section>
    </main>
  </section>
</template>

<script setup lang="ts">
import { useMemoryOverview } from './composables/useMemoryOverview'

const {
  filteredMemories,
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
} = useMemoryOverview()

function displayType(value: string | null): string {
  const labels: Record<string, string> = {
    fact: '事实',
    preference: '偏好',
    rule: '规则',
    experience: '经验',
  }
  return value ? labels[value] || value : '未分类'
}

function displaySource(value: string | null): string {
  const labels: Record<string, string> = {
    'auto-distill': 'Agent 自动蒸馏',
    'user-save': '用户保存',
    agent: 'Agent',
  }
  return value ? labels[value] || value : '未记录'
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${Math.round(value * 100)}%`
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('zh-CN')
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.memory-app {
  height: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #f6f8fa;
  color: #1f2933;
}
.memory-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 24px;
  border-bottom: 1px solid #dde5ec;
  background: #ffffff;
}
.memory-title h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
}
.memory-title span {
  display: block;
  margin-top: 4px;
  color: #667085;
  font-size: 13px;
}
.memory-search {
  min-width: min(620px, 62%);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.memory-mode {
  flex-shrink: 0;
  display: inline-flex;
  border: 1px solid #cfd8e3;
  border-radius: 6px;
  overflow: hidden;
}
.memory-mode button,
.memory-search > button,
.memory-delete {
  height: 32px;
  border: 1px solid #cfd8e3;
  background: #ffffff;
  color: #344054;
  cursor: pointer;
  font-size: 13px;
}
.memory-mode button {
  border: 0;
  border-right: 1px solid #cfd8e3;
  padding: 0 10px;
}
.memory-mode button:last-child {
  border-right: 0;
}
.memory-mode button.active {
  background: #e8f4f8;
  color: #0f6d85;
}
.memory-search input {
  flex: 1;
  min-width: 160px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #cfd8e3;
  border-radius: 6px;
  background: #ffffff;
  color: #1f2933;
  font-size: 13px;
}
.memory-search > button,
.memory-delete {
  flex-shrink: 0;
  padding: 0 12px;
  border-radius: 6px;
}
.memory-search button:hover:not(:disabled),
.memory-delete:hover:not(:disabled) {
  border-color: #2395bc;
  color: #0f6d85;
}
.memory-search button:disabled,
.memory-delete:disabled {
  opacity: 0.56;
  cursor: default;
}
.memory-message {
  flex-shrink: 0;
  padding: 8px 24px;
  border-bottom: 1px solid #d7ead4;
  background: #f2fbef;
  color: #326b24;
  font-size: 13px;
}
.memory-message--error {
  border-bottom-color: #fac5bf;
  background: #fff0ee;
  color: #b42318;
}
.memory-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(280px, 34%) minmax(0, 1fr);
}
.memory-list {
  min-width: 0;
  overflow-y: auto;
  padding: 16px;
  border-right: 1px solid #dde5ec;
  background: #f0f4f7;
}
.memory-empty {
  padding: 36px 18px;
  color: #667085;
  text-align: center;
  font-size: 14px;
  line-height: 1.6;
}
.memory-row {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
  padding: 12px;
  border: 1px solid #dde5ec;
  border-radius: 8px;
  background: #ffffff;
  color: inherit;
  cursor: pointer;
  text-align: left;
}
.memory-row:hover,
.memory-row.active {
  border-color: #2395bc;
  background: #f7fcfe;
}
.memory-row__summary {
  color: #1f2933;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.memory-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #667085;
  font-size: 12px;
}
.memory-detail {
  min-width: 0;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.memory-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.memory-detail__eyebrow {
  color: #667085;
  font-size: 12px;
}
.memory-detail h3 {
  margin: 4px 0 0;
  color: #101828;
  font-size: 20px;
  line-height: 1.35;
  word-break: break-word;
}
.memory-delete {
  border-color: #f4b5ae;
  color: #b42318;
}
.memory-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.memory-metrics div {
  min-width: 0;
  padding: 12px;
  border: 1px solid #dde5ec;
  border-radius: 8px;
  background: #ffffff;
}
.memory-metrics span,
.memory-fields dt {
  display: block;
  color: #667085;
  font-size: 12px;
}
.memory-metrics strong {
  display: block;
  margin-top: 4px;
  color: #1f2933;
  font-size: 14px;
  line-height: 1.35;
  word-break: break-word;
}
.memory-section {
  min-width: 0;
}
.memory-section h4 {
  margin: 0 0 8px;
  color: #1f2933;
  font-size: 15px;
}
.memory-section p {
  margin: 0;
  padding: 14px;
  border: 1px solid #dde5ec;
  border-radius: 8px;
  background: #ffffff;
  color: #344054;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.memory-fields {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.memory-fields div {
  min-width: 0;
  padding: 12px;
  border: 1px solid #dde5ec;
  border-radius: 8px;
  background: #ffffff;
}
.memory-fields dd {
  margin: 4px 0 0;
  color: #344054;
  font-size: 14px;
  line-height: 1.45;
  word-break: break-word;
}
.memory-detail--empty {
  align-items: center;
  justify-content: center;
  color: #667085;
  text-align: center;
}
.memory-detail--empty h3 {
  color: #344054;
}
.memory-detail--empty p {
  max-width: 420px;
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
}
@media (max-width: 920px) {
  .memory-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .memory-search {
    min-width: 0;
    width: 100%;
    flex-wrap: wrap;
    justify-content: flex-start;
  }
  .memory-body {
    grid-template-columns: 1fr;
  }
  .memory-list {
    max-height: 42%;
    border-right: 0;
    border-bottom: 1px solid #dde5ec;
  }
  .memory-metrics,
  .memory-fields {
    grid-template-columns: 1fr;
  }
}
</style>
