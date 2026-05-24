<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import { useToast } from 'primevue/usetoast'

const props = defineProps({
  agentId: { type: String, required: true },
  hostname: { type: String, default: '' },
})

const toast = useToast()
const terminalEl = ref(null)
const connecting = ref(false)
const connected = ref(false)
const form = ref({ host: '', port: '22', username: '', password: '' })

let term = null
let fitAddon = null
let socket = null
let resizeObserver = null

function wsUrl() {
  const token = localStorage.getItem('sollorm_token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/agents/${props.agentId}/ssh?token=${encodeURIComponent(token)}`
}

function setupTerminal() {
  term = new Terminal({
    cursorBlink: true,
    fontSize: 13,
    fontFamily: "'SF Mono', Monaco, Consolas, 'Courier New', monospace",
    theme: {
      background: '#0d1117',
      foreground: '#c9d1d9',
      cursor: '#58a6ff',
      selectionBackground: '#264f78',
      black: '#484f58',
      red: '#ff7b72',
      green: '#3fb950',
      yellow: '#d29922',
      blue: '#58a6ff',
      magenta: '#bc8cff',
      cyan: '#39c5cf',
      white: '#b1bac4',
    },
  })
  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.open(terminalEl.value)
  fitAddon.fit()

  term.onData((data) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'input', data }))
    }
  })

  term.onResize(({ cols, rows }) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'resize', cols, rows }))
    }
  })

  resizeObserver = new ResizeObserver(() => fitAddon?.fit())
  resizeObserver.observe(terminalEl.value)
}

function connect() {
  if (!form.value.host || !form.value.username) {
    toast.add({ severity: 'warn', summary: 'Campos obrigatórios', detail: 'Preencha host e usuário', life: 3000 })
    return
  }

  disconnect(false)
  connecting.value = true
  term.clear()
  term.writeln(`\x1b[33mConectando em ${form.value.username}@${form.value.host}:${form.value.port}...\x1b[0m`)

  socket = new WebSocket(wsUrl())

  socket.onopen = () => {
    socket.send(JSON.stringify({
      type: 'connect',
      host: form.value.host,
      port: parseInt(form.value.port) || 22,
      username: form.value.username,
      password: form.value.password,
    }))
  }

  socket.onmessage = ({ data }) => {
    const msg = JSON.parse(data)
    if (msg.type === 'connected') {
      connecting.value = false
      connected.value = true
      term.clear()
      term.focus()
      socket.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
    } else if (msg.type === 'output') {
      term.write(msg.data)
    } else if (msg.type === 'error') {
      connecting.value = false
      term.writeln(`\r\n\x1b[31m✖ ${msg.message}\x1b[0m`)
    }
  }

  socket.onerror = () => {
    connecting.value = false
    term.writeln('\r\n\x1b[31m✖ Erro na conexão WebSocket.\x1b[0m')
  }

  socket.onclose = () => {
    connecting.value = false
    connected.value = false
    socket = null
    term.writeln('\r\n\x1b[90mSessão encerrada.\x1b[0m')
  }
}

function disconnect(notify = true) {
  if (socket) {
    if (notify && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'disconnect' }))
    }
    socket.close()
    socket = null
  }
  connecting.value = false
  connected.value = false
}

onMounted(() => {
  form.value.host = props.hostname
  setupTerminal()
})

onUnmounted(() => {
  disconnect(true)
  resizeObserver?.disconnect()
  term?.dispose()
})
</script>

<template>
  <div class="ssh-terminal">
    <!-- Credentials form -->
    <div class="ssh-credentials">
      <div class="cred-row">
        <div class="cred-field cred-host">
          <label class="cred-label">Host / IP</label>
          <InputText
            v-model="form.host"
            placeholder="192.168.1.100"
            :disabled="connected || connecting"
            fluid
          />
        </div>
        <div class="cred-field cred-port">
          <label class="cred-label">Porta</label>
          <InputText
            v-model="form.port"
            placeholder="22"
            :disabled="connected || connecting"
          />
        </div>
      </div>
      <div class="cred-row">
        <div class="cred-field cred-user">
          <label class="cred-label">Usuário</label>
          <InputText
            v-model="form.username"
            placeholder="root"
            :disabled="connected || connecting"
            fluid
          />
        </div>
        <div class="cred-field cred-pass">
          <label class="cred-label">Senha</label>
          <Password
            v-model="form.password"
            placeholder="(vazio para chave SSH)"
            :feedback="false"
            toggleMask
            :disabled="connected || connecting"
            fluid
          />
        </div>
        <div class="cred-action">
          <label class="cred-label">&nbsp;</label>
          <Button
            v-if="!connected"
            label="Conectar"
            icon="pi pi-terminal"
            :loading="connecting"
            @click="connect"
          />
          <Button
            v-else
            label="Desconectar"
            icon="pi pi-times"
            severity="secondary"
            outlined
            @click="disconnect"
          />
        </div>
      </div>
    </div>

    <!-- Terminal -->
    <div class="terminal-wrapper">
      <div class="terminal-bar">
        <span class="terminal-bar-dot red" />
        <span class="terminal-bar-dot yellow" />
        <span class="terminal-bar-dot green" />
        <span class="terminal-bar-label">
          {{ connected ? `${form.username}@${form.host}` : 'Aguardando conexão' }}
        </span>
        <span v-if="connected" class="terminal-bar-status connected">● Conectado</span>
        <span v-else-if="connecting" class="terminal-bar-status connecting">◌ Conectando...</span>
      </div>
      <div ref="terminalEl" class="xterm-container" />
    </div>
  </div>
</template>

<style scoped>
.ssh-terminal {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Credentials */
.ssh-credentials {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.cred-row {
  display: flex;
  gap: 0.625rem;
  align-items: flex-end;
}

.cred-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.cred-host { flex: 1; }
.cred-port { width: 90px; }
.cred-user { flex: 1; }
.cred-pass { flex: 1; }
.cred-action { flex-shrink: 0; }

.cred-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--p-text-muted-color);
  letter-spacing: 0.02em;
}

/* Terminal chrome */
.terminal-wrapper {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
}

.terminal-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.875rem;
  background: #161b22;
  border-bottom: 1px solid #30363d;
}

.terminal-bar-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.terminal-bar-dot.red    { background: #ff5f56; }
.terminal-bar-dot.yellow { background: #ffbd2e; }
.terminal-bar-dot.green  { background: #27c93f; }

.terminal-bar-label {
  flex: 1;
  font-size: 0.75rem;
  color: #8b949e;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  margin-left: 0.5rem;
}

.terminal-bar-status {
  font-size: 0.7rem;
  font-weight: 500;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
}

.terminal-bar-status.connected  { color: #3fb950; }
.terminal-bar-status.connecting { color: #d29922; }

.xterm-container {
  height: 420px;
  background: #0d1117;
}

.xterm-container :deep(.xterm) {
  height: 100%;
  padding: 10px;
}

.xterm-container :deep(.xterm-viewport) {
  overflow-y: auto !important;
}

@media (max-width: 768px) {
  .cred-row {
    flex-direction: column;
  }
  .cred-port {
    width: 100%;
  }
}
</style>
