<template>
  <div class="office-gen-container">
    <div class="og-header">
      <h2>Office Document Generator</h2>
      <p class="og-subtitle">Generate Word, Excel, PowerPoint, and PDF documents from structured data</p>
    </div>

    <div class="og-controls">
      <label>
        Filename prefix
        <input v-model="filenamePrefix" type="text" maxlength="80" />
      </label>
    </div>

    <div class="og-grid">
      <div
        class="og-card"
        v-for="fmt in formats"
        :key="fmt.key"
      >
        <div class="og-card-icon">{{ fmt.icon }}</div>
        <div class="og-card-title">{{ fmt.name }}</div>
        <div class="og-card-desc">{{ fmt.desc }}</div>
        <div class="og-card-actions">
          <button
            type="button"
            :disabled="busy"
            @click="generateFormat(fmt.key)"
          >
            File
          </button>
          <button
            type="button"
            :disabled="busy"
            @click="generateArtifact(fmt.key)"
          >
            Artifact
          </button>
        </div>
      </div>
    </div>

    <div v-if="generatedFile" class="og-result">
      <strong>{{ generatedFile.name }}</strong>
      <span>#{{ generatedFile.file_id }} · {{ generatedFile.size }} bytes</span>
      <span>{{ generatedFile.extension }} · {{ generatedFile.deduplicated ? 'deduplicated' : 'new file' }}</span>
    </div>
    <div v-if="generatedArtifact" class="og-result">
      <strong>{{ generatedArtifact.name }}</strong>
      <span>artifact #{{ generatedArtifact.artifact_id }} · file #{{ generatedArtifact.file_id }} · {{ generatedArtifact.size }} bytes</span>
      <span>package {{ generatedArtifact.content_package_id ?? 'none' }} · {{ generatedArtifact.content_package_status }}</span>
      <span v-if="generatedArtifact.content_package_error" class="og-warning">{{ generatedArtifact.content_package_error }}</span>
    </div>
    <div v-if="errorMessage" class="og-error">{{ errorMessage }}</div>

    <div class="og-status">
      <span class="og-status-dot" :class="{ active: libreofficeOk }"></span>
      {{ busy ? 'Generating...' : libreofficeOk ? 'LibreOffice available' : 'LibreOffice not detected' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { checkHealth, generateArtifactSample, generateSample } from './api'
import type { GeneratedArtifact, GeneratedFile, OfficeFormat } from './api'

const formats: Array<{ key: OfficeFormat; name: string; icon: string; desc: string }> = [
  { key: 'docx', name: 'Word (.docx)', icon: '📄', desc: 'Generate Word documents with headings, paragraphs, tables and images' },
  { key: 'xlsx', name: 'Excel (.xlsx)', icon: '📊', desc: 'Generate spreadsheets with multiple sheets, headers and data rows' },
  { key: 'pptx', name: 'PowerPoint (.pptx)', icon: '📽️', desc: 'Generate presentations with slides, bullet points and speaker notes' },
  { key: 'pdf', name: 'PDF (.pdf)', icon: '📕', desc: 'Generate PDF documents with headings, paragraphs and tables' },
]
const libreofficeOk = ref(false)
const busy = ref(false)
const filenamePrefix = ref('office-gen-sample')
const generatedFile = ref<GeneratedFile | null>(null)
const generatedArtifact = ref<GeneratedArtifact | null>(null)
const errorMessage = ref('')

async function generateFormat(fmt: OfficeFormat) {
  busy.value = true
  generatedFile.value = null
  generatedArtifact.value = null
  errorMessage.value = ''
  try {
    generatedFile.value = await generateSample(fmt, filenamePrefix.value)
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : 'Generation failed'
  } finally {
    busy.value = false
  }
}

async function generateArtifact(fmt: OfficeFormat) {
  busy.value = true
  generatedFile.value = null
  generatedArtifact.value = null
  errorMessage.value = ''
  try {
    generatedArtifact.value = await generateArtifactSample(fmt, filenamePrefix.value)
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : 'Artifact generation failed'
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    const data = await checkHealth()
    libreofficeOk.value = !!data.libreoffice
  } catch {
    // offline
  }
})
</script>

<style scoped>
.office-gen-container {
  padding: 24px;
  color: #333;
  font-family: '苹方', 'Microsoft YaHei', '宋体', sans-serif;
}
.og-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: #2395bc;
}
.og-subtitle {
  margin: 0 0 24px;
  color: #666;
  font-size: 14px;
}
.og-controls {
  display: flex;
  margin-bottom: 16px;
}
.og-controls label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #606266;
  font-size: 12px;
}
.og-controls input {
  width: min(360px, 70vw);
  height: 30px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 0 10px;
  color: #333;
}
.og-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.og-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 20px;
  transition: all 0.2s;
  text-align: left;
}
.og-card:hover {
  border-color: #2395bc;
  box-shadow: 0 2px 12px rgba(35, 149, 188, 0.12);
}
.og-card:disabled {
  cursor: progress;
  opacity: 0.7;
}
.og-card-icon {
  font-size: 32px;
  margin-bottom: 10px;
}
.og-card-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 6px;
}
.og-card-desc {
  font-size: 12px;
  color: #999;
  line-height: 1.5;
}
.og-card-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}
.og-card-actions button {
  height: 28px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fff;
  color: #2395bc;
  cursor: pointer;
  font-size: 12px;
}
.og-card-actions button:disabled {
  color: #999;
  cursor: progress;
}
.og-status {
  font-size: 13px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
}
.og-result,
.og-error {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 13px;
}
.og-result {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid #b7eb8f;
  background: #f6ffed;
  color: #2f6f13;
}
.og-error {
  border: 1px solid #ffa39e;
  background: #fff1f0;
  color: #a8071a;
}
.og-warning {
  color: #ad6800;
}
.og-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}
.og-status-dot.active {
  background: #52c41a;
}
</style>
