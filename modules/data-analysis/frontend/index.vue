<template>
  <div class="da-app">
    <header class="da-header">
      <h2>数据分析</h2>
      <span class="da-status" :class="statusClass">{{ statusText }}</span>
    </header>

    <section class="da-body">
      <div class="da-tabs">
        <button :class="{ active: tab === 'run' }" @click="tab = 'run'">代码执行</button>
        <button :class="{ active: tab === 'chart' }" @click="tab = 'chart'">快速出图</button>
      </div>

      <div v-if="tab === 'run'" class="da-panel">
        <div class="da-field">
          <label>Python 代码 <small>（可用 pandas / numpy / matplotlib，plt.savefig() 出图）</small></label>
          <textarea v-model="code" rows="12" placeholder="import pandas as pd&#10;import numpy as np&#10;import matplotlib.pyplot as plt&#10;&#10;df = pd.DataFrame({'x': ['A','B','C'], 'y': [10, 20, 15]})&#10;df.plot(kind='bar', x='x', y='y')&#10;plt.savefig('chart.png')&#10;print(df.describe())"></textarea>
        </div>
        <div class="da-field">
          <label>输入文件 ID（逗号分隔，可选）</label>
          <input v-model="inputFiles" placeholder="例如: 42, 43" />
        </div>
        <div class="da-field">
          <label>超时（秒）</label>
          <input v-model.number="timeout" type="number" min="1" max="600" />
        </div>
        <button class="da-btn" @click="runCode" :disabled="running">{{ running ? '执行中...' : '执行' }}</button>

        <div v-if="runResult" class="da-result">
          <h3>执行结果</h3>
          <div v-if="runResult.error" class="da-error">{{ runResult.error }}</div>
          <div v-if="runResult.stdout" class="da-stdout"><pre>{{ runResult.stdout }}</pre></div>
          <div v-if="runResult.stderr" class="da-stderr"><pre>{{ runResult.stderr }}</pre></div>
          <div v-if="runResult.charts && runResult.charts.length > 0" class="da-charts">
            <h4>生成图表（{{ runResult.charts.length }} 张）</h4>
            <div v-for="c in runResult.charts" :key="c.file_id" class="da-chart-item">
              <span>{{ c.name }} ({{ (c.size / 1024).toFixed(1) }} KB)</span>
              <span class="da-chart-id">file_id: {{ c.file_id }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="tab === 'chart'" class="da-panel">
        <div class="da-field">
          <label>图表类型</label>
          <select v-model="chartType">
            <option value="line">折线图</option>
            <option value="bar">柱状图</option>
            <option value="pie">饼图</option>
          </select>
        </div>
        <div class="da-field">
          <label>标题</label>
          <input v-model="chartTitle" placeholder="图表标题（可选）" />
        </div>
        <div class="da-field">
          <label>数据（JSON 数组，每项含 x/y）</label>
          <textarea v-model="chartDataJson" rows="6" placeholder='[{"x": "一月", "y": 120}, {"x": "二月", "y": 200}]'></textarea>
        </div>
        <button class="da-btn" @click="runChart" :disabled="running">{{ running ? '生成中...' : '生成图表' }}</button>

        <div v-if="chartResult" class="da-result">
          <h3>生成结果</h3>
          <div v-if="chartResult.error" class="da-error">{{ chartResult.error }}</div>
          <div v-if="chartResult.charts && chartResult.charts.length > 0" class="da-charts">
            <h4>图表已生成</h4>
            <div v-for="c in chartResult.charts" :key="c.file_id" class="da-chart-item">
              <span>{{ c.name }} ({{ (c.size / 1024).toFixed(1) }} KB)</span>
              <span class="da-chart-id">file_id: {{ c.file_id }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { getApiUrl } from '../../data-analysis/runtime/index'

const tab = ref<'run' | 'chart'>('run')
const code = ref('')
const inputFiles = ref('')
const timeout = ref(60)
const running = ref(false)
const runResult = ref<any>(null)

const chartType = ref('line')
const chartTitle = ref('')
const chartDataJson = ref('')
const chartResult = ref<any>(null)

const statusText = computed(() => running.value ? '运行中' : '就绪')
const statusClass = computed(() => running.value ? 'running' : 'ready')

async function runCode() {
  running.value = true
  runResult.value = null
  try {
    const resp = await fetch(getApiUrl('/api/data-analysis/run'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        code: code.value,
        input_files: inputFiles.value ? inputFiles.value.split(',').map((s: string) => parseInt(s.trim(), 10)).filter((n: number) => !isNaN(n)) : [],
        timeout: timeout.value,
      }),
    })
    const json = await resp.json()
    runResult.value = json.data
  } catch (e: any) {
    runResult.value = { error: e.message }
  } finally {
    running.value = false
  }
}

async function runChart() {
  running.value = true
  chartResult.value = null
  let data: any[]
  try {
    data = JSON.parse(chartDataJson.value)
  } catch {
    chartResult.value = { error: '数据 JSON 格式错误' }
    running.value = false
    return
  }
  try {
    const resp = await fetch(getApiUrl('/api/data-analysis/chart'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        data,
        chart_type: chartType.value,
        title: chartTitle.value,
      }),
    })
    const json = await resp.json()
    chartResult.value = json.data
  } catch (e: any) {
    chartResult.value = { error: e.message }
  } finally {
    running.value = false
  }
}
</script>

<style scoped>
.da-app { height: 100%; display: flex; flex-direction: column; font-family: 苹方, "微软雅黑", 宋体, sans-serif; color: #333; }
.da-header { display: flex; align-items: center; gap: 12px; padding: 12px 20px; border-bottom: 1px solid #e8e8e8; background: #fafafa; }
.da-header h2 { margin: 0; font-size: 16px; font-weight: 600; }
.da-status { font-size: 12px; padding: 2px 8px; border-radius: 10px; }
.da-status.ready { background: #e8f5e9; color: #2e7d32; }
.da-status.running { background: #fff3e0; color: #e65100; }
.da-body { flex: 1; overflow: auto; padding: 20px; }
.da-tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 2px solid #e8e8e8; }
.da-tabs button { padding: 8px 20px; border: none; background: none; cursor: pointer; font-size: 14px; color: #666; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.da-tabs button.active { color: #2395bc; border-bottom-color: #2395bc; font-weight: 600; }
.da-panel { max-width: 800px; }
.da-field { margin-bottom: 12px; }
.da-field label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 4px; color: #555; }
.da-field label small { font-weight: normal; color: #999; }
.da-field textarea, .da-field input, .da-field select { width: 100%; padding: 8px 10px; border: 1px solid #d0d0d0; border-radius: 4px; font-size: 13px; box-sizing: border-box; }
.da-field textarea:focus, .da-field input:focus { border-color: #2395bc; outline: none; }
.da-btn { padding: 8px 24px; background: #2395bc; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.da-btn:hover { background: #31A1C6; }
.da-btn:disabled { background: #ccc; cursor: not-allowed; }
.da-result { margin-top: 16px; padding: 12px; background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 4px; }
.da-result h3 { margin: 0 0 8px; font-size: 14px; }
.da-error { color: #d32f2f; padding: 8px; background: #ffebee; border-radius: 4px; margin-bottom: 8px; }
.da-stdout pre, .da-stderr pre { margin: 0; padding: 8px; background: #f5f5f5; border-radius: 4px; font-size: 12px; overflow: auto; max-height: 300px; white-space: pre-wrap; }
.da-stderr { margin-top: 8px; }
.da-stderr pre { background: #fff3e0; }
.da-charts { margin-top: 8px; }
.da-charts h4 { margin: 0 0 8px; font-size: 13px; }
.da-chart-item { display: flex; gap: 12px; padding: 4px 0; font-size: 13px; }
.da-chart-id { color: #999; font-size: 12px; }
</style>
