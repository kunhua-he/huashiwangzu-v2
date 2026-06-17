<template>
  <div class="component-error-boundary" v-if="hasError">
    <div class="component-error-icon">⚠️</div>
    <h3 class="component-error-title">Component Error</h3>
    <p class="component-error-message">{{ errorMessage }}</p>
    <button class="component-error-retry" @click="retry">Retry</button>
  </div>
  <template v-else>
    <slot />
  </template>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const hasError = ref(false)
const errorMessage = ref('')

onErrorCaptured((err: Error) => {
  hasError.value = true
  errorMessage.value = err.message || 'An unexpected error occurred'
  console.error('[ErrorBoundary] Caught:', err)
  return false // prevent propagation
})

function retry() {
  hasError.value = false
  errorMessage.value = ''
}
</script>

<style scoped>
.component-error-boundary {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  min-height: 200px;
  text-align: center;
}
.component-error-icon {
  font-size: 32px;
  margin-bottom: 12px;
}
.component-error-title {
  font-size: 15px;
  font-weight: 600;
  color: #ef4444;
  margin: 0 0 8px;
}
.component-error-message {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 16px;
  max-width: 360px;
}
.component-error-retry {
  padding: 6px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}
.component-error-retry:hover {
  background: #f1f5f9;
}
</style>
