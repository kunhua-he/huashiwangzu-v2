<template>
  <div class="sch-stub">
    <div class="stub-card">
      <svg viewBox="0 0 48 48" fill="none" stroke="#2395bc" stroke-width="1.5" width="48" height="48">
        <circle cx="24" cy="26" r="16"/>
        <path d="M24 18v8l6 4M16 6l-6 5M32 6l6 5"/>
      </svg>
      <h3>定时任务</h3>
      <p>通过 Agent 对话创建定时/周期任务</p>
      <span class="stub-hint">打开 Agent，说「每天…提醒我」或「定时…」即可使用</span>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.sch-stub { display: flex; align-items: center; justify-content: center; height: 100%; background: var(--bg-page, #f5f6f8); }
.stub-card { text-align: center; padding: 48px; background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); max-width: 360px; }
.stub-card h3 { margin: 16px 0 8px; font-size: 18px; color: #333; }
.stub-card p { margin: 0 0 12px; color: #666; font-size: 14px; }
.stub-hint { font-size: 12px; color: #999; }
</style>
