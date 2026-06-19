<template>
  <div class="msg-row" :class="[message.role]">
    <div class="msg-avatar" :class="message.role">
      <svg v-if="message.role === 'user'" viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
        <path d="M10 10c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v1h16v-1c0-2.66-5.33-4-8-4z"/>
      </svg>
      <svg v-else viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
        <path d="M10 2C5.58 2 2 4.46 2 7.5c0 1.86 1.18 3.5 3 4.5v3l3.34-2.01c.52.14 1.08.22 1.66.22 4.42 0 8-2.46 8-5.5S14.42 2 10 2z"/>
      </svg>
    </div>
    <div class="msg-card">
      <!-- 思维过程（在气泡上方） -->
      <div v-if="message.thinking" class="inline-thinking">
        <button class="inline-th-toggle" @click="showThinking = !showThinking">
          <span class="th-indicator"></span>
          <span>思维过程</span>
          <svg :class="{ rotated: showThinking }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
            <path d="M4 3l4 3-4 3"/>
          </svg>
        </button>
        <div v-show="showThinking" class="inline-th-body">{{ message.thinking }}</div>
      </div>

      <div class="msg-bubble" :class="message.role">
        <!-- Markdown rendered content for AI, plain text for user -->
        <div v-if="message.role === 'assistant'" class="msg-md" v-html="renderedContent"></div>
        <div v-else class="msg-text">{{ message.content }}</div>
      </div>

      <!-- Reference chips -->
      <div v-if="message.references?.length" class="ref-chips">
        <button
          v-for="(r, idx) in message.references" :key="idx"
          class="ref-chip" @click="$emit('focusRef', r)"
          :title="r.title || r.source"
        >
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2" width="10" height="10">
            <path d="M2 2h3l2 2v8H4a2 2 0 01-2-2V2z"/>
            <path d="M7 4h5v8a2 2 0 01-2 2H7V4z"/>
          </svg>
          <span>{{ r.title || r.source }}</span>
        </button>
      </div>

      <!-- Tool events inline -->
      <div v-if="message.tool_events?.length" class="inline-tools">
        <button class="inline-tools-toggle" @click="showTools = !showTools">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2" width="12" height="12">
            <path d="M6.5 1.5L9 5h4l-2.5 3.5L11 12l-3.5-2L4 12l1.5-3.5L3 5h4l2.5-3.5z"/>
          </svg>
          <span>工具记录 {{ message.tool_events.length }}</span>
          <svg :class="{ rotated: showTools }" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="10" height="10">
            <path d="M4 3l4 3-4 3"/>
          </svg>
        </button>
        <div v-show="showTools" class="inline-tools-body">
          <pre>{{ formatToolResult(message.tool_events) }}</pre>
        </div>
      </div>

      <time class="msg-time">{{ formatTime(message.created_at) }}</time>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'

interface ReferenceItem { type: string; title: string; source: string; excerpt: string }
interface MsgItem {
  id: number
  role: string
  content: string
  created_at?: string | null
  thinking?: string
  references?: ReferenceItem[]
  tool_events?: unknown[]
}

const props = defineProps<{ message: MsgItem }>()
defineEmits<{ focusRef: [ref: ReferenceItem] }>()

const showThinking = ref(false)
const showTools = ref(false)

// Configure marked to use highlight.js for code blocks
const renderer = new marked.Renderer()
renderer.code = ({ text, lang }) => {
  const language = lang || ''
  let highlighted = text
  if (language && hljs.getLanguage(language)) {
    try {
      highlighted = hljs.highlight(text, { language }).value
    } catch { /* fallback */ }
  } else if (!language) {
    try { highlighted = hljs.highlightAuto(text).value } catch { /* fallback */ }
  }
  const langLabel = language ? `<span class="code-lang">${language}</span>` : ''
  return `<div class="code-block-wrapper">
    ${langLabel}
    <button class="code-copy-btn" onclick="(function(btn){var code=btn.parentElement.querySelector('code').textContent;navigator.clipboard.writeText(code);btn.textContent='已复制';setTimeout(function(){btn.textContent='复制'},1500)})(this)">复制</button>
    <pre><code class="hljs${language ? ' language-'+language : ''}">${highlighted}</code></pre>
  </div>`
}

marked.setOptions({
  renderer,
  breaks: true,
  gfm: true,
})

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  try {
    const raw = marked.parse(props.message.content, { async: false }) as string
    return DOMPurify.sanitize(raw)
  } catch {
    return props.message.content.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }
})

function formatTime(iso?: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

function formatToolResult(r: unknown): string {
  if (typeof r === 'string') return r
  try { return JSON.stringify(r, null, 2) } catch { return String(r) }
}
</script>

<style scoped>
.msg-row {
  flex-shrink: 0;
  display: flex;
  gap: var(--ag-space-md);
  margin-bottom: var(--ag-space-xl);
  animation: msgSlideUp 0.25s ease-out;
  max-width: 85%;
}
.msg-row.user { flex-direction: row-reverse; align-self: flex-end; }
.msg-row.assistant { flex-direction: row; align-self: flex-start; }

@keyframes msgSlideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Avatar */
.msg-avatar {
  flex-shrink: 0;
  width: 32px; height: 32px;
  border-radius: var(--ag-radius-full);
  display: flex; align-items: center; justify-content: center;
  margin-top: 2px;
}
.msg-avatar.user { background: var(--ag-bg-user-msg); color: var(--ag-text-white); }
.msg-avatar.assistant { background: var(--ag-primary-light); color: var(--ag-primary); }

/* Card */
.msg-card { display: flex; flex-direction: column; gap: var(--ag-space-xs); min-width: 0; }
.msg-row.user .msg-card { align-items: flex-end; }
.msg-row.assistant .msg-card { align-items: flex-start; }

/* Bubble */
.msg-bubble {
  padding: var(--ag-space-md) var(--ag-space-lg);
  line-height: var(--ag-line-height-relaxed);
  font-size: var(--ag-font-size-md);
  word-break: break-word;
  overflow-wrap: break-word;
}
.msg-bubble.user {
  background: var(--ag-bg-user-msg);
  color: var(--ag-text-white);
  border-radius: var(--ag-radius-xl) var(--ag-radius-sm) var(--ag-radius-xl) var(--ag-radius-xl);
}
.msg-bubble.assistant {
  background: var(--ag-bg-assistant-msg);
  border: 1px solid var(--ag-border-light);
  border-radius: var(--ag-radius-sm) var(--ag-radius-xl) var(--ag-radius-xl) var(--ag-radius-xl);
  box-shadow: var(--ag-shadow-sm);
}

/* Markdown content */
.msg-md :deep(p) { margin: 0 0 var(--ag-space-sm); }
.msg-md :deep(p:last-child) { margin-bottom: 0; }
.msg-md :deep(ul), .msg-md :deep(ol) { padding-left: 20px; margin: var(--ag-space-sm) 0; }
.msg-md :deep(li) { margin: 2px 0; }
.msg-md :deep(blockquote) {
  border-left: 3px solid var(--ag-primary);
  padding-left: var(--ag-space-md);
  margin: var(--ag-space-sm) 0;
  color: var(--ag-text-secondary);
}
.msg-md :deep(a) { color: var(--ag-text-link); text-decoration: none; }
.msg-md :deep(a:hover) { text-decoration: underline; }
.msg-md :deep(h1), .msg-md :deep(h2), .msg-md :deep(h3), .msg-md :deep(h4) {
  margin: var(--ag-space-lg) 0 var(--ag-space-sm);
  font-weight: 600; line-height: var(--ag-line-height-tight);
}
.msg-md :deep(h1) { font-size: 1.3em; }
.msg-md :deep(h2) { font-size: 1.15em; }
.msg-md :deep(h3) { font-size: 1.05em; }
.msg-md :deep(hr) { border: none; border-top: 1px solid var(--ag-border-light); margin: var(--ag-space-md) 0; }
.msg-md :deep(table) { border-collapse: collapse; margin: var(--ag-space-sm) 0; width: 100%; }
.msg-md :deep(th), .msg-md :deep(td) {
  border: 1px solid var(--ag-border-light); padding: var(--ag-space-sm) var(--ag-space-md);
  font-size: var(--ag-font-size-sm);
}
.msg-md :deep(th) { background: var(--ag-bg-page); font-weight: 600; }
.msg-md :deep(strong) { font-weight: 600; }
.msg-md :deep(em) { font-style: italic; }

/* Inline code */
.msg-md :deep(code:not(pre code)) {
  background: var(--ag-bg-page);
  padding: 1px 5px;
  border-radius: var(--ag-radius-sm);
  font-size: 0.9em;
  font-family: var(--ag-font-mono);
}
.msg-bubble.user .msg-md :deep(code:not(pre code)) { background: rgba(255,255,255,0.2); }

/* Code blocks */
.msg-md :deep(.code-block-wrapper) {
  position: relative;
  background: #1E1E2E;
  border-radius: var(--ag-radius-lg);
  margin: var(--ag-space-sm) 0;
  overflow: hidden;
}
.msg-md :deep(.code-lang) {
  position: absolute;
  top: 8px; left: 12px;
  font-size: var(--ag-font-size-xs);
  color: rgba(255,255,255,0.4);
  font-family: var(--ag-font-mono);
  text-transform: uppercase;
  pointer-events: none;
}
.msg-md :deep(.code-copy-btn) {
  position: absolute;
  top: 6px; right: 8px;
  padding: 2px 8px;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: var(--ag-radius-sm);
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.6);
  font-size: var(--ag-font-size-xs);
  cursor: pointer;
  transition: all var(--ag-transition-fast);
}
.msg-md :deep(.code-copy-btn:hover) {
  background: rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.9);
}
.msg-md :deep(pre) { margin: 0; padding: 0; }
.msg-md :deep(pre code) {
  display: block;
  padding: 32px var(--ag-space-lg) var(--ag-space-lg);
  overflow-x: auto;
  font-family: var(--ag-font-mono);
  font-size: var(--ag-font-size-sm);
  line-height: var(--ag-line-height-base);
  color: #CDD6F4;
}

/* User bubble overrides for markdown */
.msg-bubble.user .msg-md :deep(a) { color: rgba(255,255,255,0.85); text-decoration: underline; }
.msg-bubble.user .msg-md :deep(blockquote) { border-left-color: rgba(255,255,255,0.4); color: rgba(255,255,255,0.8); }
.msg-bubble.user .msg-md :deep(code:not(pre code)) { background: rgba(255,255,255,0.15); }
.msg-bubble.user .msg-md :deep(th) { background: rgba(255,255,255,0.1); }
.msg-bubble.user .msg-md :deep(th), .msg-bubble.user .msg-md :deep(td) { border-color: rgba(255,255,255,0.2); }

/* Plain text */
.msg-text {
  white-space: pre-wrap;
  line-height: var(--ag-line-height-relaxed);
}

/* Inline thinking (above the bubble) */
.inline-thinking {
  margin-bottom: var(--ag-space-sm);
  padding-bottom: var(--ag-space-sm);
  border-bottom: 1px solid var(--ag-border-light);
  width: 100%;
}
.inline-th-toggle {
  display: flex; align-items: center; gap: 5px;
  border: none; background: none; cursor: pointer;
  font-size: var(--ag-font-size-sm); color: var(--ag-text-tertiary);
  padding: 2px 0; transition: color var(--ag-transition-fast);
}
.inline-th-toggle:hover { color: var(--ag-text-secondary); }
.th-indicator {
  width: 6px; height: 6px; border-radius: var(--ag-radius-full);
  background: var(--ag-warning); flex-shrink: 0;
}
.inline-th-toggle svg { transition: transform var(--ag-transition-base); }
.inline-th-toggle svg.rotated { transform: rotate(90deg); }
.inline-th-body {
  font-size: var(--ag-font-size-sm);
  color: var(--ag-text-secondary);
  margin-top: var(--ag-space-xs);
  padding: var(--ag-space-sm) var(--ag-space-md);
  background: var(--ag-bg-page);
  border-radius: var(--ag-radius-md);
  white-space: pre-wrap;
  line-height: var(--ag-line-height-base);
}

/* Reference chips */
.ref-chips {
  display: flex; gap: var(--ag-space-xs); flex-wrap: wrap;
  margin-top: var(--ag-space-sm);
  padding-top: var(--ag-space-sm);
  border-top: 1px solid var(--ag-border-light);
}
.ref-chip {
  display: flex; align-items: center; gap: 3px;
  padding: 3px 8px;
  border: 1px solid var(--ag-border-light);
  border-radius: 20px;
  background: var(--ag-bg-page);
  color: var(--ag-text-link);
  font-size: var(--ag-font-size-sm);
  cursor: pointer;
  transition: all var(--ag-transition-fast);
  max-width: 200px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ref-chip:hover { background: var(--ag-primary-light); border-color: var(--ag-primary); }
.ref-chip span { overflow: hidden; text-overflow: ellipsis; }

/* Tool events inline */
.inline-tools {
  margin-top: var(--ag-space-sm);
  padding-top: var(--ag-space-sm);
  border-top: 1px solid var(--ag-border-light);
}
.inline-tools-toggle {
  display: flex; align-items: center; gap: 5px;
  border: none; background: none; cursor: pointer;
  font-size: var(--ag-font-size-sm); color: var(--ag-text-tertiary);
  padding: 2px 0; transition: color var(--ag-transition-fast);
}
.inline-tools-toggle:hover { color: var(--ag-text-secondary); }
.inline-tools-toggle svg { transition: transform var(--ag-transition-base); }
.inline-tools-toggle svg.rotated { transform: rotate(90deg); }
.inline-tools-body {
  margin-top: var(--ag-space-xs);
}
.inline-tools-body pre {
  white-space: pre-wrap; word-break: break-all;
  max-height: 200px; overflow: auto;
  background: var(--ag-bg-page);
  padding: var(--ag-space-sm) var(--ag-space-md);
  border-radius: var(--ag-radius-md);
  font-size: var(--ag-font-size-sm);
  font-family: var(--ag-font-mono);
  color: var(--ag-text-secondary);
}

/* Time */
.msg-time {
  font-size: var(--ag-font-size-xs);
  color: var(--ag-text-tertiary);
  margin-top: 2px;
}
</style>
