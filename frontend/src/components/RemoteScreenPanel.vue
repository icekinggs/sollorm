<script setup>
import { ref, onUnmounted } from 'vue'
import Button from 'primevue/button'

const props = defineProps({
  agentId: { type: String, required: true },
})

const canvasEl   = ref(null)
const connected  = ref(false)
const connecting = ref(false)
const error      = ref('')

let ws        = null
let ctx       = null
const imgObj  = new Image()
let keysBound = false

function wsUrl() {
  const token    = localStorage.getItem('sollorm_token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/agents/${props.agentId}/remote-screen?token=${encodeURIComponent(token)}&fps=12&quality=65`
}

function connect() {
  error.value      = ''
  connecting.value = true

  ws = new WebSocket(wsUrl())

  ws.onopen = () => {
    connecting.value = false
    connected.value  = true
    bindInput()
  }

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.type === 'remote_frame') {
      drawFrame(msg.data, msg.width, msg.height)
    } else if (msg.type === 'error') {
      error.value = msg.message || 'Erro na conexão'
      _close()
    }
  }

  ws.onerror = () => {
    error.value      = 'Falha ao conectar ao agente'
    connecting.value = false
    _close()
  }

  ws.onclose = () => {
    connecting.value = false
    connected.value  = false
    unbindInput()
  }
}

function disconnect() {
  ws?.close()
  _close()
}

function _close() {
  ws        = null
  connected.value  = false
  connecting.value = false
  unbindInput()
}

function drawFrame(b64, width, height) {
  if (!canvasEl.value) return
  if (!ctx) ctx = canvasEl.value.getContext('2d')
  if (canvasEl.value.width !== width)   canvasEl.value.width  = width
  if (canvasEl.value.height !== height) canvasEl.value.height = height
  imgObj.onload = () => ctx.drawImage(imgObj, 0, 0)
  imgObj.src    = 'data:image/jpeg;base64,' + b64
}

// ── Mouse ──────────────────────────────────────────────────────────────────

function normalised(e) {
  const r = canvasEl.value.getBoundingClientRect()
  return {
    x: (e.clientX - r.left)  / r.width,
    y: (e.clientY - r.top)   / r.height,
  }
}

function sendMouse(e, event) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  const { x, y } = normalised(e)
  ws.send(JSON.stringify({ type: 'remote_mouse', x, y, event, button: e.button ?? 0 }))
}

const onMouseMove = (e) => sendMouse(e, 'move')
const onMouseDown = (e) => sendMouse(e, 'down')
const onMouseUp   = (e) => sendMouse(e, 'up')
const onCtxMenu   = (e) => e.preventDefault()

// ── Keyboard ───────────────────────────────────────────────────────────────

function onKeyDown(e) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  e.preventDefault()
  ws.send(JSON.stringify({ type: 'remote_key', code: e.code, event: 'down' }))
}

function onKeyUp(e) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  e.preventDefault()
  ws.send(JSON.stringify({ type: 'remote_key', code: e.code, event: 'up' }))
}

function bindInput() {
  if (keysBound) return
  keysBound = true
  document.addEventListener('keydown', onKeyDown)
  document.addEventListener('keyup',   onKeyUp)
}

function unbindInput() {
  if (!keysBound) return
  keysBound = false
  document.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('keyup',   onKeyUp)
}

onUnmounted(() => { disconnect() })
</script>

<template>
  <div class="rs-panel">

    <!-- ── Start screen ── -->
    <div v-if="!connected && !connecting" class="rs-start">
      <div class="rs-start-icon"><i class="pi pi-desktop" /></div>
      <p class="rs-start-label">Captura de tela nativa</p>
      <p class="rs-start-hint">Controle o desktop do agente diretamente pelo navegador.</p>
      <p v-if="error" class="rs-error">{{ error }}</p>
      <Button label="Iniciar Acesso Remoto" icon="pi pi-play" @click="connect" />
    </div>

    <!-- ── Connecting ── -->
    <div v-if="connecting" class="rs-status">
      <i class="pi pi-spin pi-spinner" />
      <span>Iniciando captura de tela...</span>
    </div>

    <!-- ── Toolbar ── -->
    <div v-if="connected" class="rs-toolbar">
      <span class="rs-label"><i class="pi pi-circle-fill rs-dot" /> Acesso Remoto Ativo</span>
      <Button label="Desconectar" icon="pi pi-times" size="small" severity="danger" text @click="disconnect" />
    </div>

    <!-- ── Canvas ── -->
    <div class="rs-viewport" :class="{ active: connected }">
      <canvas
        ref="canvasEl"
        class="rs-canvas"
        tabindex="0"
        @mousemove="onMouseMove"
        @mousedown="onMouseDown"
        @mouseup="onMouseUp"
        @contextmenu="onCtxMenu"
      />
    </div>

  </div>
</template>

<style scoped>
.rs-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

/* Start */
.rs-start {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2.5rem 1rem;
  text-align: center;
}

.rs-start-icon {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: var(--p-surface-100, rgba(255,255,255,0.06));
  border: 1px solid var(--p-content-border-color);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.5rem;
  color: var(--p-primary-color);
  margin-bottom: 0.25rem;
}

.rs-start-label {
  font-weight: 600;
  font-size: 1rem;
  margin: 0;
}

.rs-start-hint {
  font-size: 0.82rem;
  color: var(--p-text-muted-color);
  margin: 0 0 0.5rem;
}

.rs-error {
  font-size: 0.82rem;
  color: var(--p-red-400);
  margin: 0 0 0.25rem;
}

/* Status */
.rs-status {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  font-size: 0.875rem;
  color: var(--p-text-muted-color);
}

.rs-status i { color: var(--p-primary-color); }

/* Toolbar */
.rs-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.5rem;
  background: var(--p-surface-50, rgba(255,255,255,0.03));
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
}

.rs-label {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.rs-dot {
  font-size: 0.5rem;
  color: var(--p-green-400);
  filter: drop-shadow(0 0 4px var(--p-green-400));
}

/* Viewport */
.rs-viewport {
  display: none;
  width: 100%;
  border-radius: 6px;
  overflow: hidden;
  background: #000;
}

.rs-viewport.active {
  display: block;
  min-height: 500px;
}

.rs-canvas {
  display: block;
  width: 100%;
  height: auto;
  cursor: crosshair;
}

.rs-canvas:focus { outline: none; }
</style>
