<template>
  <div class="input-area">
    <div class="input-container">
      <textarea
        ref="textareaRef"
        v-model="text"
        class="input-box"
        :placeholder="placeholder"
        :disabled="sending"
        @keydown.enter.exact="handleSend"
        @input="autoResize"
        rows="1"
      ></textarea>
      <div class="input-actions">
        <span class="input-hint">Enter 发送 · Shift+Enter 换行</span>
        <button
          v-if="sending"
          class="btn-stop"
          @click="handleSend"
          title="停止生成"
        >
          <svg viewBox="0 0 14 14" fill="currentColor" width="14" height="14">
            <rect x="2" y="2" width="10" height="10" rx="1.5"/>
          </svg>
          停止
        </button>
        <button
          v-else
          class="btn-send"
          :disabled="!canSend"
          @click="handleSend"
          title="发送"
        >
          <svg viewBox="0 0 18 18" fill="currentColor" width="16" height="16">
            <path d="M2 2l14 7L2 16V2z"/>
            <path d="M7 9h7" stroke="#fff" stroke-width="1.5"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'

const props = defineProps<{
  modelValue: string
  sending: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  stop: []
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const text = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const placeholder = '输入消息…'

const canSend = computed(() => text.value.trim().length > 0 && !props.sending && !props.disabled)

function handleSend() {
  if (props.sending) { emit('stop'); return }
  if (canSend.value) emit('send')
}

function autoResize() {
  nextTick(() => {
    const el = textareaRef.value
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(Math.max(el.scrollHeight, 36), 160) + 'px'
    }
  })
}

function focus() {
  textareaRef.value?.focus()
}

defineExpose({ focus })

onMounted(() => autoResize())
watch(() => props.modelValue, () => autoResize())
</script>

<style scoped>
.input-area {
  padding: 12px 20px 14px;
  background: var(--ag-bg-base);
  border-top: 1px solid var(--ag-border-light);
  flex-shrink: 0;
}

.input-container {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  gap: 10px;
  align-items: flex-end;
  background: var(--ag-bg-base);
  border: 1.5px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  padding: 6px 6px 6px 18px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input-container:focus-within {
  border-color: var(--ag-primary);
  box-shadow: 0 0 0 3px rgba(0, 134, 168, 0.1), 0 4px 16px rgba(15, 23, 42, 0.06);
}

.input-box {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-family: var(--ag-font-family);
  font-size: var(--ag-font-size-md);
  line-height: 1.55;
  color: var(--ag-text-primary);
  resize: none;
  min-height: 36px;
  max-height: 160px;
  padding: 6px 0;
}

.input-box::placeholder { color: var(--ag-text-placeholder); }
.input-box:disabled { opacity: 0.5; cursor: not-allowed; }

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding-bottom: 5px;
}

.input-hint {
  display: none;
  font-size: var(--ag-font-size-xs);
  color: var(--ag-text-tertiary);
  white-space: nowrap;
  user-select: none;
}

@media (min-width: 520px) {
  .input-hint { display: inline; }
}

.btn-send {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  background: var(--ag-primary);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.btn-send:hover:not(:disabled) {
  background: var(--ag-primary-dark);
  transform: scale(1.04);
}

.btn-send:disabled {
  background: var(--ag-border-light);
  color: var(--ag-text-tertiary);
  cursor: not-allowed;
  transform: none;
}

.btn-stop {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  border: 1px solid #FCA5A5;
  border-radius: 10px;
  background: #FEF2F2;
  color: #DC2626;
  cursor: pointer;
  font-size: var(--ag-font-size-sm);
  font-weight: 500;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn-stop:hover {
  background: #FEE2E2;
  border-color: #F87171;
}
</style>
