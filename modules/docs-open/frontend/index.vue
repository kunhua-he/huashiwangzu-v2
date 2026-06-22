<template>
  <viewer-shell file-name="文档开放接口" app-name="文档开放接口" :show-save="false" :show-download="false">
    <template #toolbar-extra></template>
    <div class="doc-container">
      <div class="doc-card">
        <h2>文档开放接口</h2>
        <p class="subtitle">仿腾讯文档 OpenAPI 设计 · 自托管 · 令牌三件套</p>

        <section>
          <h3>使用方式</h3>
          <p class="desc">文档开放接口提供 RESTful API 和可嵌入编辑器，供其他模块/Agent/内部页面调用。</p>
        </section>

        <section>
          <h3>令牌三件套</h3>
          <table class="api-table">
            <tr><td class="label">X-Client-Id</td><td>调用方标识（应用/模块名）</td></tr>
            <tr><td class="label">X-Open-Id</td><td>用户标识（用户 ID）</td></tr>
            <tr><td class="label">X-Access-Token</td><td>文档访问令牌（POST /api/docs/token 签发）</td></tr>
          </table>
        </section>

        <section>
          <h3>API 端点</h3>
          <table class="api-table">
            <tr><td class="method post">POST</td><td>/api/docs/token</td><td>签发文档令牌</td></tr>
            <tr><td class="method post">POST</td><td>/api/docs/open</td><td>打开文档 → embed_url</td></tr>
            <tr><td class="method post">POST</td><td>/api/docs</td><td>创建文档</td></tr>
            <tr><td class="method get">GET</td><td>/api/docs/{id}/content</td><td>读结构化 JSON</td></tr>
            <tr><td class="method post">POST</td><td>/api/docs/{id}/content</td><td>写回结构化 JSON</td></tr>
            <tr><td class="method get">GET</td><td>/api/docs/embed/{id}?token=...</td><td>嵌入编辑器页面</td></tr>
          </table>
        </section>

        <section>
          <h3>Embed URL 映射表</h3>
          <table class="api-table">
            <tr><th>格式</th><th>嵌入方式</th></tr>
            <tr><td>xlsx/xls</td><td>结构化 JSON → HTML 表格（读/写）</td></tr>
            <tr><td>csv</td><td>CSV 文本 → textarea（读/写）</td></tr>
            <tr><td>txt/md/json/yaml等</td><td>纯文本 → textarea（读/写）</td></tr>
            <tr><td>pdf</td><td>iframe → 原生 PDF 查看器</td></tr>
            <tr><td>docx/doc</td><td>iframe → 原生文档查看器</td></tr>
            <tr><td>pptx/ppt</td><td>iframe → 原生演示查看器</td></tr>
            <tr><td>png/jpg/gif等</td><td>img 标签 → 图片</td></tr>
          </table>
        </section>

        <section>
          <h3>快速测试</h3>
          <div class="test-row">
            <input v-model="testFileId" placeholder="输入 file_id" type="number" class="test-input" />
            <button class="test-btn" @click="testOpen">打开文档</button>
          </div>
          <div v-if="testResult" class="test-result">
            <pre>{{ JSON.stringify(testResult, null, 2) }}</pre>
          </div>
        </section>
      </div>
    </div>
    <template #statusbar>
      <span>docs-open v1.0.0</span>
    </template>
  </viewer-shell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import viewerShell from '@/shared/components/viewer-shell.vue'
import { platform } from '../runtime'

const testFileId = ref<number>(0)
const testResult = ref<unknown>(null)

async function testOpen() {
  if (!testFileId.value) return
  try {
    const result = await platform.docs.open(testFileId.value, 'view')
    testResult.value = result
  } catch (e: unknown) {
    testResult.value = { success: false, error: e instanceof Error ? e.message : String(e) }
  }
}
</script>

<style scoped>
.doc-container {
  padding: 24px;
  overflow-y: auto;
  height: 100%;
  background: #f5f7fa;
}

.doc-card {
  max-width: 800px;
  margin: 0 auto;
  background: #fff;
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

h2 {
  font-size: 22px;
  color: #303133;
  margin: 0 0 4px;
}

.subtitle {
  color: #909399;
  font-size: 13px;
  margin: 0 0 28px;
}

section {
  margin-bottom: 24px;
}

h3 {
  font-size: 15px;
  color: #303133;
  margin: 0 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}

.desc {
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

.api-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.api-table th, .api-table td {
  padding: 6px 10px;
  border: 1px solid #ebeef5;
  text-align: left;
}

.api-table th {
  background: #f5f7fa;
  color: #606266;
  font-weight: 500;
}

.api-table .label {
  font-weight: 600;
  color: #2395bc;
  font-family: monospace;
}

.method {
  font-weight: 600;
  font-family: monospace;
  text-align: center;
  width: 60px;
}

.method.post { color: #67c23a; }
.method.get { color: #2395bc; }

.test-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.test-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
  outline: none;
}

.test-input:focus {
  border-color: #2395bc;
}

.test-btn {
  padding: 8px 20px;
  background: #2395bc;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}

.test-btn:hover {
  background: #31A1C6;
}

.test-result {
  margin-top: 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  overflow-x: auto;
}

.test-result pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #303133;
}
</style>
