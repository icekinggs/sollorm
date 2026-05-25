<script setup>
import { ref, onUnmounted, nextTick } from 'vue'
import Guacamole from 'guacamole-common-js'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'

const props = defineProps({
  agentId:     { type: String, required: true },
  defaultHost: { type: String, default: '' },
})

const displayEl  = ref(null)
const connected  = ref(false)
const connecting = ref(false)
const error      = ref('')

const form = ref({
  host:     props.defaultHost,
  port:     3389,
  username: '',
  password: '',
  domain:   '',
})

let client   = null
let keyboard = null
let mouse    = null

function wsBase() {
  const token    = localStorage.getItem('sollorm_token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/agents/${props.agentId}/rdp?token=${encodeURIComponent(token)}`
}

async function connect() {
  if (!form.value.host || !form.value.username) {
    error.value = 'Host e usuário são obrigatórios'
    return
  }
  error.value   = ''
  connecting.value = true

  await nextTick()
  const W = displayEl.value ? Math.max(800, displayEl.value.offsetWidth) : 1280
  const H = 720

  const tunnel = new Guacamole.WebSocketTunnel(wsBase())
  client = new Guacamole.Client(tunnel)

  // Mount display canvas
  displayEl.value.innerHTML = ''
  displayEl.value.appendChild(client.getDisplay().getElement())

  // Scale on resize
  client.getDisplay().onresize = (w, h) => {
    if (displayEl.value && w) {
      client.getDisplay().scale(
        Math.min(displayEl.value.offsetWidth / w, 1)
      )
    }
  }

  // Mouse
  mouse = new Guacamole.Mouse(client.getDisplay().getElement())
  mouse.onEach(
    ['mousedown', 'mouseup', 'mousemove', 'mouseout'],
    (e) => client.sendMouseState(e.state, true)
  )

  // Keyboard (bind to document so shortcuts work)
  keyboard = new Guacamole.Keyboard(document)
  keyboard.onkeydown = (ks) => client.sendKeyEvent(1, ks)
  keyboard.onkeyup   = (ks) => client.sendKeyEvent(0, ks)

  client.onstatechange = (state) => {
    // 3 = CONNECTED, 5 = DISCONNECTED
    if (state === 3) { connecting.value = false; connected.value = true }
    if (state === 5) { connecting.value = false; connected.value = false }
  }

  client.onerror = (err) => {
    connecting.value = false
    connected.value  = false
    error.value      = err?.message || 'Falha na conexão RDP'
    _cleanup()
  }

  const params = new URLSearchParams({
    host:     form.value.host,
    port:     String(form.value.port),
    username: form.value.username,
    password: form.value.password,
    domain:   form.value.domain,
    width:    String(W),
    height:   String(H),
  }).toString()

  client.connect(params)
}

function disconnect() {
  client?.disconnect()
  _cleanup()
  connected.value  = false
  connecting.value = false
}

function _cleanup() {
  keyboard?.reset()
  keyboard = null
  mouse    = null
  client   = null
}

function sendCtrlAltDel() {
  if (!client) return
  const XK_Control_L = 0xffe3
  const XK_Alt_L     = 0xffe9
  const XK_Delete    = 0xffff
  client.sendKeyEvent(1, XK_Control_L)
  client.sendKeyEvent(1, XK_Alt_L)
  client.sendKeyEvent(1, XK_Delete)
  client.sendKeyEvent(0, XK_Delete)
  client.sendKeyEvent(0, XK_Alt_L)
  client.sendKeyEvent(0, XK_Control_L)
}

onUnmounted(() => { client?.disconnect(); _cleanup() })
</script>

<template>
  <div class="rdp-panel">

    <!-- ── Connection form ── -->
    <div v-if="!connected && !connecting" class="rdp-form">
      <div class="form-grid">
        <div class="field">
          <label>Host / IP</label>
          <InputText v-model="form.host" placeholder="192.168.1.10" @keyup.enter="connect" />
        </div>
        <div class="field field-sm">
          <label>Porta</label>
          <InputNumber v-model="form.port" :min="1" :max="65535" :use-grouping="false" />
        </div>
        <div class="field">
          <label>Usuário</label>
          <InputText v-model="form.username" placeholder="Administrador" @keyup.enter="connect" />
        </div>
        <div class="field">
          <label>Senha</label>
          <InputText v-model="form.password" type="password" @keyup.enter="connect" />
        </div>
        <div class="field">
          <label>Domínio <span class="optional">(opcional)</span></label>
          <InputText v-model="form.domain" placeholder="WORKGROUP" @keyup.enter="connect" />
        </div>
        <div class="field field-action">
          <Button label="Conectar" icon="pi pi-desktop" @click="connect" />
        </div>
      </div>
      <p v-if="error" class="form-error">{{ error }}</p>
    </div>

    <!-- ── Connecting ── -->
    <div v-if="connecting" class="rdp-status">
      <i class="pi pi-spin pi-spinner" />
      <span>Conectando ao RDP em <strong>{{ form.host }}</strong>...</span>
      <Button label="Cancelar" text size="small" @click="disconnect" />
    </div>

    <!-- ── Toolbar when connected ── -->
    <div v-if="connected" class="rdp-toolbar">
      <span class="rdp-host-label">
        <i class="pi pi-desktop" /> {{ form.username }}@{{ form.host }}
      </span>
      <div class="rdp-actions">
        <Button
          label="Ctrl+Alt+Del"
          icon="pi pi-lock"
          size="small"
          severity="secondary"
          text
          @click="sendCtrlAltDel"
        />
        <Button
          label="Desconectar"
          icon="pi pi-times"
          size="small"
          severity="danger"
          text
          @click="disconnect"
        />
      </div>
    </div>

    <!-- ── Display ── -->
    <div
      ref="displayEl"
      class="rdp-display"
      :class="{ active: connected }"
    />

  </div>
</template>

<style scoped>
.rdp-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

/* Form */
.rdp-form { padding: 0.25rem 0; }

.form-grid {
  display: grid;
  grid-template-columns: 1fr 100px 1fr 1fr 1fr auto;
  gap: 0.625rem;
  align-items: end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.field label {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  font-weight: 500;
}

.optional { font-weight: 400; opacity: 0.7; }

.field :deep(input),
.field :deep(.p-inputnumber-input) {
  width: 100%;
  font-size: 0.875rem;
}

.field-sm { min-width: 0; }

.field-action { padding-bottom: 1px; }

.form-error {
  margin: 0.5rem 0 0;
  font-size: 0.82rem;
  color: var(--p-red-400);
}

/* Status */
.rdp-status {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  font-size: 0.875rem;
  color: var(--p-text-muted-color);
}

.rdp-status i { color: var(--p-primary-color); }

/* Toolbar */
.rdp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.5rem;
  background: var(--p-surface-50, rgba(255,255,255,0.03));
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
}

.rdp-host-label {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.rdp-actions { display: flex; gap: 0.25rem; }

/* Display */
.rdp-display {
  width: 100%;
  min-height: 0;
  overflow: hidden;
  border-radius: 6px;
  background: #000;
  display: none;
}

.rdp-display.active {
  display: block;
  min-height: 500px;
}

.rdp-display :deep(canvas) {
  display: block;
  max-width: 100%;
}

/* Responsive */
@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr 1fr;
  }
  .field-action { grid-column: 1 / -1; }
}
</style>
