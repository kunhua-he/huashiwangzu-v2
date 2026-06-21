<template>
  <div class="image-gen-stub">
    <div class="stub-card">
      <svg viewBox="0 0 48 48" fill="none" stroke="#2395bc" stroke-width="1.5" width="48" height="48">
        <rect x="6" y="6" width="36" height="36" rx="4"/>
        <circle cx="18" cy="18" r="4"/>
        <path d="M6 34l10-10 8 8 6-4 12 10v4a2 2 0 01-2 2H8a2 2 0 01-2-2v-8z"/>
      </svg>
      <h3>图片生成</h3>
      <p>通过 Agent 对话即可生成图片</p>
      <span class="stub-hint">打开 Agent 应用，输入"生成一张..."即可使用</span>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.image-gen-stub {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--bg-page, #f5f6f8);
}
.stub-card {
  text-align: center;
  padding: 48px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  max-width: 360px;
}
.stub-card h3 {
  margin: 16px 0 8px;
  font-size: 18px;
  color: #333;
}
.stub-card p {
  margin: 0 0 12px;
  color: #666;
  font-size: 14px;
}
.stub-hint {
  font-size: 12px;
  color: #999;
}
</style>
