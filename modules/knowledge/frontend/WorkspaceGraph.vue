<template>
  <div class="workspace-graph" ref="containerRef">
    <!-- Three.js canvas -->
    <canvas ref="canvasRef" class="graph-canvas"></canvas>

    <!-- HUD overlay layer -->
    <div class="hud-overlay" v-if="engineReady">
      <!-- Corner brackets -->
      <div class="corner-brackets">
        <div class="cb cb-tl"><span></span><span></span></div>
        <div class="cb cb-tr"><span></span><span></span></div>
        <div class="cb cb-bl"><span></span><span></span></div>
        <div class="cb cb-br"><span></span><span></span></div>
      </div>

      <!-- Top-left title -->
      <div class="hud-title">
        <h1>知识网络全景</h1>
        <span class="hud-subtitle">KNOWLEDGE CONSTELLATION</span>
      </div>

      <!-- Top-right stats -->
      <div class="hud-stats">
        <span class="stat-nodes">{{ nodeCount }} 节点</span>
        <span class="stat-divider">·</span>
        <span class="stat-edges">{{ edgeCount }} 关联</span>
      </div>

      <!-- Bottom-right legend panel -->
      <div class="hud-legend">
        <div class="legend-item" v-for="item in legendItems" :key="item.label">
          <span class="legend-dot" :style="{ background: item.color }"></span>
          <span class="legend-label">{{ item.label }}</span>
        </div>
      </div>

      <!-- Bottom-left tooltip -->
      <div class="hud-tooltip" v-if="tooltipNode">
        <div class="tt-name">{{ tooltipNode.label }}</div>
        <div class="tt-meta">{{ tooltipTypeLabel }} · {{ tooltipEdgeCount }} 关联</div>
      </div>
    </div>

    <!-- Scanline overlay -->
    <div class="scanline-overlay" v-if="engineReady"></div>
    <!-- Vignette -->
    <div class="vignette-overlay" v-if="engineReady"></div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <span>星图加载中…</span>
    </div>

    <!-- Empty state -->
    <div v-if="!loading && nodeCount === 0" class="empty-overlay">
      <span class="empty-icon">✦</span>
      <span>尚无关联数据。上传并分析多份资料后自动织网。</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { GraphEngine } from './graph3d/GraphEngine'
import { computeLayout } from './graph3d/layout3d'
import { theme, getNodeColor, getNodeRadius, nodeTypeVisualMap } from './graph3d/theme'
import { NodeType, type GraphNode, type GraphEdge } from './graph3d/types'
import { getApiUrl } from '../runtime'

const emit = defineEmits<{
  select: [node: GraphNode]
}>()

// ── Engine refs ──
const containerRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const engine = ref<GraphEngine | null>(null)
const engineReady = ref(false)
const loading = ref(true)

// ── Data ──
const nodes = ref<GraphNode[]>([])
const edges = ref<GraphEdge[]>([])
const nodeCount = computed(() => nodes.value.length)
const edgeCount = computed(() => edges.value.length)

// ── Tooltip ──
const tooltipNode = ref<GraphNode | null>(null)
const tooltipTypeLabel = computed(() => {
  if (!tooltipNode.value) return ''
  return typeLabels[tooltipNode.value.type] ?? tooltipNode.value.type
})
const tooltipEdgeCount = computed(() => {
  if (!tooltipNode.value) return 0
  return edges.value.filter(e => e.source === tooltipNode.value!.id || e.target === tooltipNode.value!.id).length
})

// ── Legend ──
const legendItems = computed(() => {
  const types = new Set(nodes.value.map(n => n.type))
  const items: { label: string; color: string }[] = []
  for (const type of types) {
    const color = getNodeColor(type)
    const label = typeLabels[type] ?? type
    items.push({ label, color: color.hex })
  }
  // Sort: subject/concept/tag/brand/document/unknown
  const order = [NodeType.Subject, NodeType.Concept, NodeType.Tag, NodeType.Brand, NodeType.Document, NodeType.Unknown]
  items.sort((a, b) => {
    const ai = order.indexOf(a.label.toLowerCase() as any)
    const bi = order.indexOf(b.label.toLowerCase() as any)
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
  })
  return items.slice(0, 6)
})

// ── Type labels ──
const typeLabels: Record<string, string> = {
  [NodeType.Subject]: '主体',
  [NodeType.Concept]: '概念',
  [NodeType.Tag]: '标签',
  [NodeType.Brand]: '品牌',
  [NodeType.Document]: '文件',
  [NodeType.Unknown]: '未知',
}

// ── Resize Observer ──
let resizeObserver: ResizeObserver | null = null
let visibilityObserver: IntersectionObserver | null = null

// ── Load data from API ──
async function loadData() {
  loading.value = true
  try {
    // Try entity-graph first, fall back to relation-graph
    const res = await fetch(getApiUrl('/knowledge/entity-graph'), {
      headers: authHeaders(),
    })
    const body = await res.json()
    if (body.success && body.data?.nodes?.length) {
      const data = body.data
      // Map backend nodes to graph format (normalize category→type)
      const graphNodes: GraphNode[] = (data.nodes || []).map((n: any) => ({
        id: n.id,
        label: n.label,
        type: mapCategoryToType(n.category || n.type || 'unknown'),
        weight: 0,
      }))
      const graphEdges: GraphEdge[] = (data.edges || []).map((e: any) => ({
        source: e.source,
        target: e.target,
        weight: e.weight ?? e.similarity_score ?? 0.5,
        relation: e.relation ?? '',
      }))

      if (graphNodes.length > 0) {
        nodes.value = graphNodes
        edges.value = graphEdges
        applyData()
        return
      }
    }

    // Fallback: relation-graph
    const res2 = await fetch(getApiUrl('/knowledge/relation-graph'), {
      headers: authHeaders(),
    })
    const body2 = await res2.json()
    if (body2.success && body2.data?.nodes?.length) {
      const data = body2.data
      const graphNodes: GraphNode[] = (data.nodes || []).map((n: any) => ({
        id: n.id,
        label: n.label,
        type: n.type || NodeType.Document,
        weight: 0,
      }))
      const graphEdges: GraphEdge[] = (data.edges || []).map((e: any) => ({
        source: e.source,
        target: e.target,
        weight: e.weight ?? e.similarity_score ?? 0.5,
        relation: e.relation_type ?? '',
      }))

      nodes.value = graphNodes
      edges.value = graphEdges
      applyData()
    } else {
      // No data
      nodes.value = []
      edges.value = []
      loading.value = false
    }
  } catch (e) {
    console.error('[WorkspaceGraph] load error:', e)
    nodes.value = []
    edges.value = []
    loading.value = false
  }
}

function applyData() {
  if (!engine.value) return
  try {
    engine.value.setData(nodes.value, edges.value)
    engineReady.value = true
    loading.value = false
  } catch (e) {
    console.error('[WorkspaceGraph] applyData error:', e)
    loading.value = false
  }
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('v2_auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function mapCategoryToType(category: string): string {
  const lower = (category || '').toLowerCase()
  const map: Record<string, string> = {
    '主体': NodeType.Subject,
    'subject': NodeType.Subject,
    '核心实体': NodeType.Subject,
    '概念': NodeType.Concept,
    '术语': NodeType.Concept,
    'concept': NodeType.Concept,
    '标签': NodeType.Tag,
    '属性': NodeType.Tag,
    'tag': NodeType.Tag,
    '品牌': NodeType.Brand,
    '产品': NodeType.Brand,
    'brand': NodeType.Brand,
    '文件': NodeType.Document,
    'document': NodeType.Document,
  }
  return map[lower] ?? NodeType.Unknown
}

// ── Lifecycle ──
onMounted(async () => {
  await nextTick()
  const canvas = canvasRef.value
  if (!canvas) return

  // Create engine
  const g = new GraphEngine(canvas, {
    backgroundColor: '#030812',
    bloomStrength: 0.6,
    bloomRadius: 0.4,
    bloomThreshold: 0.1,
    labelDistanceThreshold: 120,
    downgradeThreshold: 500,
  })

  // Listen for events
  g.on('select', (event: any) => {
    if (event?.node) {
      tooltipNode.value = event.node
      emit('select', event.node)
    }
  })
  g.on('hover', (event: any) => {
    tooltipNode.value = event?.node ?? null
  })

  g.init()
  engine.value = g

  // Visibility observer — pause RAF when hidden
  const container = containerRef.value
  if (container) {
    visibilityObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            g.resume()
          } else {
            g.pause()
          }
        }
      },
      { threshold: 0 },
    )
    visibilityObserver.observe(container)
  }

  // Resize observer
  resizeObserver = new ResizeObserver(() => {
    g.resize()
  })
  resizeObserver.observe(canvas.parentElement!)

  // Load data
  await loadData()
})

onUnmounted(() => {
  visibilityObserver?.disconnect()
  resizeObserver?.disconnect()
  engine.value?.dispose()
  engine.value = null
})
</script>

<style scoped>
.workspace-graph {
  flex: 1;
  min-height: 200px;
  position: relative;
  background: #030812;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid #1a2d42;
}

.graph-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

/* ── HUD overlay ── */
.hud-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 10;
}

/* ── Corner brackets ── */
.corner-brackets { position: absolute; inset: 0; }
.cb { position: absolute; width: 24px; height: 24px; }
.cb span { display: block; position: absolute; background: rgba(104,168,255,0.35); }
.cb span:first-child { width: 16px; height: 2px; }
.cb span:last-child { width: 2px; height: 16px; }

.cb-tl { top: 14px; left: 14px; }
.cb-tl span:first-child { top: 0; left: 0; }
.cb-tl span:last-child { top: 8px; left: 0; }

.cb-tr { top: 14px; right: 14px; }
.cb-tr span:first-child { top: 0; right: 0; }
.cb-tr span:last-child { top: 8px; right: 0; }

.cb-bl { bottom: 14px; left: 14px; }
.cb-bl span:first-child { bottom: 0; left: 0; }
.cb-bl span:last-child { bottom: 8px; left: 0; }

.cb-br { bottom: 14px; right: 14px; }
.cb-br span:first-child { bottom: 0; right: 0; }
.cb-br span:last-child { bottom: 8px; right: 0; }

/* ── Title ── */
.hud-title {
  position: absolute;
  top: 16px;
  left: 44px;
}
.hud-title h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  font-family: 'Orbitron', 'system-ui', sans-serif;
  color: #e2edff;
  letter-spacing: 1px;
  text-shadow: 0 0 20px rgba(104,168,255,0.3);
}
.hud-subtitle {
  font-size: 9px;
  color: rgba(104,168,255,0.5);
  letter-spacing: 3px;
  font-family: 'Orbitron', 'system-ui', sans-serif;
  display: block;
  margin-top: 2px;
}

/* ── Stats ── */
.hud-stats {
  position: absolute;
  top: 20px;
  right: 44px;
  font-size: 11px;
  color: rgba(162, 192, 230, 0.6);
  letter-spacing: 0.5px;
  font-variant-numeric: tabular-nums;
}
.stat-divider { margin: 0 6px; opacity: 0.4; }

/* ── Legend ── */
.hud-legend {
  position: absolute;
  bottom: 44px;
  right: 20px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(4,12,28,0.92);
  border: 1px solid rgba(54,82,128,0.28);
  backdrop-filter: blur(14px);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
  box-shadow: 0 0 4px currentColor;
}
.legend-label {
  font-size: 11px;
  color: #bccbe0;
  font-family: 'system-ui', sans-serif;
}

/* ── Tooltip ── */
.hud-tooltip {
  position: absolute;
  bottom: 44px;
  left: 20px;
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(4,12,28,0.92);
  border: 1px solid rgba(54,82,128,0.28);
  backdrop-filter: blur(14px);
  pointer-events: none;
}
.tt-name {
  font-size: 13px;
  font-weight: 600;
  color: #e2edff;
}
.tt-meta {
  font-size: 10px;
  color: #7c8da0;
  margin-top: 2px;
}

/* ── Scanline overlay ── */
.scanline-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 5;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(255,255,255,0.018) 2px,
    rgba(255,255,255,0.018) 4px
  );
}

/* ── Vignette ── */
.vignette-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 4;
  background: radial-gradient(ellipse at center, transparent 60%, rgba(1,4,8,0.6) 100%);
}

/* ── Loading ── */
.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(162,192,230,0.6);
  font-size: 13px;
  background: #030812;
  z-index: 20;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(104,168,255,0.15);
  border-top-color: rgba(104,168,255,0.7);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty ── */
.empty-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: rgba(162,192,230,0.5);
  font-size: 13px;
  z-index: 20;
  background: #030812;
}
.empty-icon {
  font-size: 28px;
  opacity: 0.4;
}
</style>
