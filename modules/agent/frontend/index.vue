<template>
  <div class="agent-app agent-theme">
    <ConversationSidebar
      :conversations="conversations"
      :activeConvId="activeConvId"
      :loading="loading"
      :collapsed="sidebarCollapsed"
      @select="selectConversation"
      @new="newConversation"
      @rename="renameConversation"
      @delete="deleteConversation"
      @toggle="sidebarCollapsed = !sidebarCollapsed"
    />

    <section class="agent-main">
      <ChatToolbar
        :profiles="profiles"
        :profileKey="profileKey"
        :refPanelVisible="showReferencePanel"
        @update:profileKey="profileKey = $event"
        @toggleRef="showReferencePanel = !showReferencePanel"
        @newConv="newConversation"
      />

      <!-- 消息区域 -->
      <div class="msg-area" ref="msgArea">
        <div v-if="!activeConvId && !loading" class="msg-empty">
          <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1" width="40" height="40" class="msg-empty-icon">
            <circle cx="24" cy="24" r="20"/><path d="M24 16v12M18 22h12"/><path d="M16 32l3-3h10l3 3"/>
          </svg>
          <p>选择或创建一个对话开始</p>
        </div>
        <div v-if="messages.length === 0 && activeConvId && !loading" class="msg-empty">
          <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1" width="40" height="40" class="msg-empty-icon">
            <path d="M8 10h32v24H16l-8 6V10z"/>
          </svg>
          <p>开始对话吧</p>
          <span class="msg-empty-hint">发送消息开启对话</span>
        </div>

        <template v-for="(m, i) in messages" :key="`${m.id}-${i}`">
          <ToolCallCard v-if="m.eventType === 'tool_call' || m.eventType === 'tool_result'" :message="m" />
          <ThinkingCard v-else-if="m.eventType === 'thinking'" :content="m.content" :running="streaming" />
          <MessageBubble v-else :message="m" @focusRef="focusReference" />
        </template>

        <!-- 流式输出指示器 -->
        <div v-if="streaming" class="msg-row streaming">
          <div class="streaming-ai">
            <div class="msg-avatar assistant">
              <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
                <path d="M10 2C5.58 2 2 4.46 2 7.5c0 1.86 1.18 3.5 3 4.5v3l3.34-2.01c.52.14 1.08.22 1.66.22 4.42 0 8-2.46 8-5.5S14.42 2 10 2z"/>
              </svg>
            </div>
            <div class="streaming-content">
              <div class="streaming-text">{{ streamingText || '思考中...' }}</div>
              <span class="streaming-cursor">|</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 引用面板 -->
      <ReferencePanel
        v-if="showReferencePanel"
        :references="allReferences"
        :activeRef="activeReference"
        @select="(r: RefItem) => activeReference = r"
      />

      <InputArea ref="inputAreaRef" v-model="inputText" :sending="sending" @send="sendMessage" />

      <p v-if="error" class="error-text">{{ error }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, onMounted } from 'vue'
import { initRuntime, getApiUrl, authHeaders } from '../runtime'
import ConversationSidebar from './components/ConversationSidebar.vue'
import ChatToolbar from './components/ChatToolbar.vue'
import InputArea from './components/InputArea.vue'
import MessageBubble from './components/MessageBubble.vue'
import ThinkingCard from './components/ThinkingCard.vue'
import ToolCallCard from './components/ToolCallCard.vue'
import ReferencePanel from './components/ReferencePanel.vue'
import './components/style-variables.css'

// ── 类型 ──
interface ConvItem { id: number; title: string; status?: string }
interface ModelProfile { key: string; name: string; provider: string; model: string }
interface RefItem { type: string; title: string; source: string; excerpt: string }
interface ApiBody<T> { success: boolean; data: T; error?: string | null }
interface MsgItem { id: number; role: string; content: string; created_at?: string | null; eventType?: string; toolName?: string; toolResult?: unknown; thinking?: string; references?: RefItem[]; tool_events?: unknown[] }

// ── 状态 ──
const conversations = ref<ConvItem[]>([])
const profiles = ref<ModelProfile[]>([])
const tools = ref<unknown[]>([])
const activeConvId = ref<number | null>(null)
const messages = ref<MsgItem[]>([])
const inputText = ref('')
const sending = ref(false)
const streaming = ref(false)
const streamingText = ref('')
const loading = ref(false)
const error = ref('')
const sidebarCollapsed = ref(false)
const showReferencePanel = ref(false)
const activeReference = ref<RefItem | null>(null)
const msgArea = ref<HTMLElement | null>(null)
const inputAreaRef = ref<InstanceType<typeof InputArea> | null>(null)
const profileKey = ref('deepseek-v4-flash')
const allReferences = computed<RefItem[]>(() => {
  const result: RefItem[] = []
  for (const m of messages.value) {
    if (m.references?.length) result.push(...m.references)
  }
  return result
})

// ── API helper ──
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = getApiUrl(path)
  const r = await fetch(url, { headers: { ...init?.headers as Record<string, string> || {}, ...authHeaders() }, ...init })
  const body: ApiBody<T> = await r.json()
  if (!body.success) throw new Error(body.error || '请求失败')
  return body.data as T
}

async function apiFetchRaw(path: string, init?: RequestInit): Promise<Response> {
  const url = getApiUrl(path)
  return fetch(url, { headers: { ...init?.headers as Record<string, string> || {}, ...authHeaders() }, ...init })
}

// ── Conv operations ──
async function loadConversations() {
  conversations.value = await apiFetch<ConvItem[]>('/agent/conversations')
}
async function newConversation() {
  const item = await apiFetch<ConvItem>('/agent/conversations', { method: 'POST', body: JSON.stringify({ title: '新对话' }), headers: { 'Content-Type': 'application/json' } })
  conversations.value.unshift(item)
  await selectConversation(item.id)
}
async function renameConversation(p: ConvItem) {
  await apiFetch(`/agent/conversations/${p.id}`, { method: 'PATCH', body: JSON.stringify({ title: p.title }), headers: { 'Content-Type': 'application/json' } })
  const found = conversations.value.find(c => c.id === p.id)
  if (found) found.title = p.title
}
async function deleteConversation(item: ConvItem) {
  await apiFetch(`/agent/conversations/${item.id}`, { method: 'DELETE' })
  conversations.value = conversations.value.filter(c => c.id !== item.id)
  if (activeConvId.value === item.id) { messages.value = []; activeConvId.value = null }
}

async function selectConversation(id: number) {
  activeConvId.value = id; messages.value = []; showReferencePanel.value = false; error.value = ''
  try { messages.value = await apiFetch<MsgItem[]>(`/agent/conversations/${id}/messages`) } catch { /* ignore */ }
  nextTick(scrollToBottom)
}

// ── Scroll ──
function scrollToBottom() {
  nextTick(() => { if (msgArea.value) msgArea.value.scrollTop = msgArea.value.scrollHeight })
}

function focusReference(ref: RefItem) {
  activeReference.value = ref; showReferencePanel.value = true
}

// ── Metadata ──
async function loadMetadata() {
  try {
    const [p, t] = await Promise.all([
      apiFetch<ModelProfile[]>('/agent/profiles'),
      apiFetch<unknown[]>('/agent/tools'),
    ])
    profiles.value = p
    tools.value = t
  } catch (e: unknown) { error.value = '加载配置失败: ' + String((e as Error).message || e) }
}

// ── Chat ──
async function sendMessage() {
  if (sending.value || !activeConvId.value) return
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  sending.value = true; streaming.value = true; streamingText.value = ''; error.value = ''
  messages.value.push({ id: 0, role: 'user', content: text, created_at: new Date().toISOString() })
  scrollToBottom()
  try {
    const resp = await apiFetchRaw('/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: activeConvId.value, content: text, profile_key: profileKey.value }),
    })
    if (!resp.ok) { error.value = `请求失败 (${resp.status})`; streaming.value = false; return }
    if (!resp.body) { error.value = '无响应体'; streaming.value = false; return }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      for (const line of chunk.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        const payload = trimmed.slice(6)
        if (payload === '[DONE]') { streaming.value = false; await reloadMessages(activeConvId.value!); scrollToBottom(); continue }
        const evt = JSON.parse(payload)
        if (evt.type === 'content') { streaming.value = false; messages.value.push({ id: 0, role: 'assistant', content: evt.content || '', created_at: new Date().toISOString() }) }
        else if (evt.type === 'thinking') {
          const chunk: string = evt.content || ''
          streamingText.value += chunk
          const last = messages.value[messages.value.length - 1]
          if (last && last.eventType === 'thinking') {
            last.content += chunk
          } else {
            messages.value.push({ id: 0, role: '', content: chunk, eventType: 'thinking' })
          }
        }
        else if (evt.type === 'tool_call') { messages.value.push({ id: 0, role: '', content: '', eventType: 'tool_call', toolName: evt.name }) }
        else if (evt.type === 'tool_result') { messages.value.push({ id: 0, role: '', content: '', eventType: 'tool_result', toolName: evt.name, toolResult: evt.result }) }
        else if (evt.type === 'token') { streamingText.value += evt.content || '' }
        else if (evt.type === 'error') { streaming.value = false; error.value = evt.content || '流式错误' }
        scrollToBottom()
      }
    }
  } catch (e: unknown) { error.value = String((e as Error).message || e); streaming.value = false }
  finally { sending.value = false; inputAreaRef.value?.focus() }
}

async function reloadMessages(convId: number) { try { messages.value = await apiFetch<MsgItem[]>(`/agent/conversations/${convId}/messages`) } catch { /* ignore */ } }

onMounted(async () => { await initRuntime('agent'); await Promise.all([loadMetadata(), loadConversations()]); if (conversations.value.length === 0) await newConversation(); else await selectConversation(conversations.value[0].id) })
</script>

<style scoped>
.agent-app { display: flex; height: 100%; overflow: hidden; }
.agent-main { flex: 1; display: flex; flex-direction: column; min-width: 0; position: relative; background: var(--ag-bg-page); }

/* ── Messages ── */
.msg-area { flex: 1; overflow-y: auto; padding: var(--ag-space-xl) var(--ag-space-lg); display: flex; flex-direction: column; }
.msg-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; color: var(--ag-text-tertiary); gap: var(--ag-space-sm); }
.msg-empty-icon { opacity: 0.25; }
.msg-empty p { margin: 0; font-size: var(--ag-font-size-md); }
.msg-empty-hint { font-size: var(--ag-font-size-sm); }

/* ── Streaming row ── */
.msg-row.streaming { display: flex; gap: var(--ag-space-md); margin-bottom: var(--ag-space-xl); animation: msgSlideUp 0.25s ease-out; }
@keyframes msgSlideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.streaming-ai { display: flex; gap: var(--ag-space-md); max-width: 85%; }
.streaming-content { display: flex; align-items: flex-start; gap: 2px; padding: var(--ag-space-md) var(--ag-space-lg); border-radius: var(--ag-radius-sm) var(--ag-radius-xl) var(--ag-radius-xl) var(--ag-radius-xl); background: var(--ag-bg-assistant-msg); border: 1px solid var(--ag-border-light); box-shadow: var(--ag-shadow-sm); font-size: var(--ag-font-size-md); line-height: var(--ag-line-height-relaxed); min-width: 80px; }
.streaming-text { white-space: pre-wrap; word-break: break-word; }
.streaming-cursor { animation: blink 1s step-end infinite; color: var(--ag-primary); font-weight: 700; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* ── Shared avatar (for streaming) ── */
.msg-avatar { flex-shrink: 0; width: 32px; height: 32px; border-radius: var(--ag-radius-full); display: flex; align-items: center; justify-content: center; margin-top: 2px; }
.msg-avatar.assistant { background: var(--ag-primary-light); color: var(--ag-primary); }

/* ── Error ── */
.error-text { margin: 0; padding: var(--ag-space-sm) var(--ag-space-lg) var(--ag-space-md); color: var(--ag-error); font-size: var(--ag-font-size-sm); background: var(--ag-bg-base); }
</style>
