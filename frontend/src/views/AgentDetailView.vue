<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { agentsApi } from '@/api/agents'
import {
  formatBytes,
  formatRelativeDate,
  formatDateTime,
  formatUptime,
  usageColorClass
} from '@/composables/useFormatters'

import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useConfirm } from 'primevue/useconfirm'
import ConfirmDialog from 'primevue/confirmdialog'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'

const props = defineProps({
  id: { type: String, required: true }
})

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const deleting = ref(false)

const agent = ref(null)
const heartbeats = ref([])
const executions = ref([])
const loading = ref(true)
const refreshInterval = ref(null)
const executing = ref(false)
const sshVisible = ref(false)
const sshConnecting = ref(false)
const sshConnected = ref(false)
const sshOutput = ref('')
const sshInput = ref('')
const sshSocket = ref(null)
const sshForm = ref({
  host: '',
  port: 22,
  username: '',
  password: ''
})
const scriptForm = ref({
  language: 'bash',
  script: 'hostname\nwhoami',
  timeout_seconds: 60
})

const scriptLanguages = [
  { label: 'Bash', value: 'bash' },
  { label: 'PowerShell', value: 'powershell' },
  { label: 'Python', value: 'python' }
]

const lastHeartbeat = computed(() => heartbeats.value[0] || null)

async function loadData() {
  try {
    const [agentRes, hbRes, execRes] = await Promise.all([
      agentsApi.get(props.id),
      agentsApi.heartbeats(props.id, 20),
      agentsApi.executions(props.id, 20)
    ])
    agent.value = agentRes.data
    heartbeats.value = hbRes.data
    executions.value = execRes.data
    if (!sshForm.value.host) {
      sshForm.value.host = agentRes.data.hostname || ''
    }
  } catch (err) {
    if (err.response?.status === 404) {
      toast.add({
        severity: 'error',
        summary: 'Não encontrado',
        detail: 'Agente não existe',
        life: 3000
      })
      router.push('/dashboard')
    } else {
      toast.add({
        severity: 'error',
        summary: 'Erro',
        detail: 'Falha ao carregar dados do agente',
        life: 4000
      })
    }
  } finally {
    loading.value = false
  }
}

function executionSeverity(status) {
  if (status === 'succeeded') return 'success'
  if (status === 'running') return 'info'
  if (status === 'pending' || status === 'queued') return 'warn'
  return 'danger'
}

function openRemoteAccess() {
  sshVisible.value = true
}

function sshWebSocketUrl() {
  const token = localStorage.getItem('sollorm_token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = `${window.location.hostname}:8000`
  const query = new URLSearchParams({ token })
  return `${protocol}//${host}/api/v1/agents/${props.id}/ssh?${query.toString()}`
}

function appendSshOutput(text) {
  sshOutput.value += text
}

function connectSsh() {
  if (!sshForm.value.host || !sshForm.value.username) {
    toast.add({
      severity: 'warn',
      summary: 'SSH incompleto',
      detail: 'Informe host e usuário',
      life: 3000
    })
    return
  }

  disconnectSsh(false)
  sshConnecting.value = true
  sshOutput.value = ''

  const socket = new WebSocket(sshWebSocketUrl())
  sshSocket.value = socket

  socket.onopen = () => {
    socket.send(JSON.stringify({
      type: 'connect',
      host: sshForm.value.host,
      port: sshForm.value.port,
      username: sshForm.value.username,
      password: sshForm.value.password
    }))
  }

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data)
    if (message.type === 'connected') {
      sshConnecting.value = false
      sshConnected.value = true
      appendSshOutput('SSH conectado.\n')
    } else if (message.type === 'output') {
      appendSshOutput(message.data)
    } else if (message.type === 'error') {
      sshConnecting.value = false
      appendSshOutput(`\n${message.message}\n`)
    }
  }

  socket.onerror = () => {
    sshConnecting.value = false
    appendSshOutput('\nErro na conexão SSH.\n')
  }

  socket.onclose = () => {
    sshConnecting.value = false
    sshConnected.value = false
    if (sshSocket.value === socket) {
      sshSocket.value = null
    }
  }
}

function disconnectSsh(sendClose = true) {
  if (sshSocket.value) {
    if (sendClose && sshSocket.value.readyState === WebSocket.OPEN) {
      sshSocket.value.send(JSON.stringify({ type: 'disconnect' }))
    }
    sshSocket.value.close()
  }
  sshSocket.value = null
  sshConnecting.value = false
  sshConnected.value = false
}

function sendSshInput() {
  if (!sshConnected.value || !sshSocket.value || !sshInput.value) return
  sshSocket.value.send(JSON.stringify({
    type: 'input',
    data: `${sshInput.value}\n`
  }))
  appendSshOutput(`$ ${sshInput.value}\n`)
  sshInput.value = ''
}

async function runScript() {
  if (!scriptForm.value.script.trim()) {
    toast.add({
      severity: 'warn',
      summary: 'Script vazio',
      detail: 'Digite um script para executar',
      life: 3000
    })
    return
  }

  executing.value = true
  try {
    await agentsApi.createExecution(props.id, {
      language: scriptForm.value.language,
      script: scriptForm.value.script,
      timeout_seconds: scriptForm.value.timeout_seconds
    })
    toast.add({
      severity: 'success',
      summary: 'Execução criada',
      detail: 'O comando foi enviado para o agente',
      life: 3000
    })
    await loadData()
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Erro',
      detail: err.response?.data?.detail || 'Falha ao executar script',
      life: 4000
    })
  } finally {
    executing.value = false
  }
}

function handleDelete() {
  if (!agent.value) return

  confirm.require({
    message: `Tem certeza que deseja apagar o agente "${agent.value.hostname}"?

Isso vai:
- Apagar todo o histórico de heartbeats
- Apagar o token de instalação
- A máquina vai parar de reportar até ser reinstalada

Esta ação NÃO pode ser desfeita.`,
    header: 'Confirmar exclusão',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    acceptLabel: 'Sim, apagar',
    rejectLabel: 'Cancelar',
    accept: async () => {
      deleting.value = true
      try {
        await agentsApi.delete(props.id)
        toast.add({
          severity: 'success',
          summary: 'Agente apagado',
          detail: `"${agent.value.hostname}" foi removido do sistema`,
          life: 3000
        })
        if (refreshInterval.value) clearInterval(refreshInterval.value)
        router.push('/dashboard')
      } catch (err) {
        deleting.value = false
        toast.add({
          severity: 'error',
          summary: 'Erro',
          detail: err.response?.data?.detail || 'Falha ao apagar agente',
          life: 4000
        })
      }
    }
  })
}

onMounted(() => {
  loadData()
  refreshInterval.value = setInterval(loadData, 30000)
})

onUnmounted(() => {
  if (refreshInterval.value) clearInterval(refreshInterval.value)
  disconnectSsh()
})
</script>

<template>
  <div class="agent-detail">
    <div class="page-header">
      <Button
        icon="pi pi-arrow-left"
        text
        rounded
        @click="router.push('/dashboard')"
        aria-label="Voltar"
      />
      <h2 v-if="agent">{{ agent.hostname }}</h2>
      <h2 v-else>Carregando...</h2>
      <Tag
        v-if="agent"
        :value="agent.is_online ? 'Online' : 'Offline'"
        :severity="agent.is_online ? 'success' : 'secondary'"
      />
      <div class="header-spacer"></div>
      <Button
        v-if="agent?.os !== 'windows'"
        label="Conectar SSH"
        icon="pi pi-terminal"
        outlined
        @click="openRemoteAccess"
      />
      <Button
        v-if="agent"
        label="Apagar agente"
        icon="pi pi-trash"
        severity="danger"
        outlined
        :loading="deleting"
        @click="handleDelete"
      />
    </div>
    <ConfirmDialog />

    <div v-if="loading" class="loading-state">
      <ProgressSpinner style="width: 32px; height: 32px" stroke-width="4" />
    </div>

    <div v-else-if="agent" class="content-grid">
      <div class="card">
        <h3>Métricas atuais</h3>
        <div v-if="lastHeartbeat" class="metrics-row">
          <div class="metric-block">
            <div class="metric-label">CPU</div>
            <div class="metric-value">{{ lastHeartbeat.cpu_usage_percent.toFixed(1) }}%</div>
            <div class="usage-bar">
              <div
                class="usage-bar-fill"
                :class="usageColorClass(lastHeartbeat.cpu_usage_percent)"
                :style="{ width: lastHeartbeat.cpu_usage_percent + '%' }"
              ></div>
            </div>
          </div>
          <div class="metric-block">
            <div class="metric-label">RAM</div>
            <div class="metric-value">{{ lastHeartbeat.ram_usage_percent.toFixed(1) }}%</div>
            <div class="usage-bar">
              <div
                class="usage-bar-fill"
                :class="usageColorClass(lastHeartbeat.ram_usage_percent)"
                :style="{ width: lastHeartbeat.ram_usage_percent + '%' }"
              ></div>
            </div>
          </div>
          <div class="metric-block">
            <div class="metric-label">Disco</div>
            <div class="metric-value">{{ lastHeartbeat.disk_usage_percent.toFixed(1) }}%</div>
            <div class="usage-bar">
              <div
                class="usage-bar-fill"
                :class="usageColorClass(lastHeartbeat.disk_usage_percent)"
                :style="{ width: lastHeartbeat.disk_usage_percent + '%' }"
              ></div>
            </div>
          </div>
          <div class="metric-block">
            <div class="metric-label">Uptime</div>
            <div class="metric-value">{{ formatUptime(lastHeartbeat.uptime_seconds) }}</div>
          </div>
        </div>
        <p v-else class="text-muted">Nenhum heartbeat recebido ainda.</p>
      </div>

      <div class="card">
        <h3>Informações do sistema</h3>
        <table class="info-table">
          <tbody>
            <tr>
              <td class="text-muted">ID</td>
              <td class="mono">{{ agent.id }}</td>
            </tr>
            <tr>
              <td class="text-muted">Sistema</td>
              <td>{{ agent.platform || '—' }}</td>
            </tr>
            <tr>
              <td class="text-muted">SO</td>
              <td>{{ agent.os || '—' }}</td>
            </tr>
            <tr>
              <td class="text-muted">CPU</td>
              <td>{{ agent.cpu_model || '—' }} ({{ agent.cpu_cores }} cores)</td>
            </tr>
            <tr>
              <td class="text-muted">RAM total</td>
              <td>{{ formatBytes(agent.ram_total_bytes) }}</td>
            </tr>
            <tr>
              <td class="text-muted">Disco total</td>
              <td>{{ formatBytes(agent.disk_total_bytes) }}</td>
            </tr>
            <tr>
              <td class="text-muted">Versão do agente</td>
              <td>{{ agent.agent_version || '—' }}</td>
            </tr>
            <tr>
              <td class="text-muted">Primeira conexão</td>
              <td>{{ formatDateTime(agent.first_seen) }}</td>
            </tr>
            <tr>
              <td class="text-muted">Última conexão</td>
              <td>{{ formatRelativeDate(agent.last_seen) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card full-width">
        <h3>Acesso SSH</h3>
        <div v-if="sshVisible" class="ssh-panel">
          <div class="ssh-toolbar">
            <InputText
              v-model="sshForm.host"
              placeholder="Host ou IP"
              class="ssh-host"
            />
            <InputNumber
              v-model="sshForm.port"
              :min="1"
              :max="65535"
              class="ssh-port"
            />
            <InputText
              v-model="sshForm.username"
              placeholder="Usuário"
              class="ssh-user"
            />
            <Password
              v-model="sshForm.password"
              placeholder="Senha"
              :feedback="false"
              toggle-mask
              class="ssh-password"
            />
            <Button
              v-if="!sshConnected"
              label="Conectar"
              icon="pi pi-link"
              :loading="sshConnecting"
              @click="connectSsh"
            />
            <Button
              v-else
              label="Desconectar"
              icon="pi pi-times"
              severity="secondary"
              outlined
              @click="disconnectSsh"
            />
          </div>
          <pre class="ssh-terminal mono">{{ sshOutput || 'Aguardando conexão SSH...' }}</pre>
          <div class="ssh-input-row">
            <InputText
              v-model="sshInput"
              placeholder="Digite um comando e pressione Enter"
              :disabled="!sshConnected"
              fluid
              @keyup.enter="sendSshInput"
            />
            <Button
              icon="pi pi-send"
              :disabled="!sshConnected"
              @click="sendSshInput"
              aria-label="Enviar comando SSH"
            />
          </div>
        </div>
        <p v-else class="text-muted">Clique em Conectar SSH para abrir uma sessão nativa no navegador.</p>
      </div>

      <div class="card full-width">
        <h3>Execução remota</h3>
        <div class="script-runner">
          <div class="script-toolbar">
            <Select
              v-model="scriptForm.language"
              :options="scriptLanguages"
              option-label="label"
              option-value="value"
              class="language-select"
            />
            <InputNumber
              v-model="scriptForm.timeout_seconds"
              :min="1"
              :max="3600"
              suffix="s"
              show-buttons
              class="timeout-input"
            />
            <Button
              label="Executar"
              icon="pi pi-play"
              :loading="executing"
              @click="runScript"
            />
          </div>
          <Textarea
            v-model="scriptForm.script"
            rows="8"
            auto-resize
            class="script-editor mono"
          />
        </div>
      </div>

      <div class="card full-width">
        <h3>Histórico de execuções</h3>
        <DataTable
          :value="executions"
          :rows="20"
          striped-rows
          class="execution-table"
        >
          <Column field="created_at" header="Criado em" style="width: 190px">
            <template #body="{ data }">
              {{ formatDateTime(data.created_at) }}
            </template>
          </Column>
          <Column field="language" header="Tipo" style="width: 120px">
            <template #body="{ data }">
              <code class="mono">{{ data.language }}</code>
            </template>
          </Column>
          <Column field="status" header="Status" style="width: 130px">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="executionSeverity(data.status)" />
            </template>
          </Column>
          <Column field="exit_code" header="Exit" style="width: 80px">
            <template #body="{ data }">
              {{ data.exit_code ?? '—' }}
            </template>
          </Column>
          <Column header="Saída">
            <template #body="{ data }">
              <div class="execution-output">
                <pre v-if="data.stdout" class="mono">{{ data.stdout }}</pre>
                <pre v-if="data.stderr" class="mono stderr">{{ data.stderr }}</pre>
                <span v-if="!data.stdout && !data.stderr" class="text-muted">
                  {{ data.error_message || 'Sem saída ainda' }}
                </span>
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

      <div class="card full-width">
        <h3>Histórico recente de heartbeats</h3>
        <DataTable
          :value="heartbeats"
          :rows="20"
          striped-rows
          class="hb-table"
        >
          <Column field="received_at" header="Recebido em" style="width: 200px">
            <template #body="{ data }">
              {{ formatDateTime(data.received_at) }}
            </template>
          </Column>
          <Column field="cpu_usage_percent" header="CPU">
            <template #body="{ data }">
              {{ data.cpu_usage_percent.toFixed(1) }}%
            </template>
          </Column>
          <Column field="ram_usage_percent" header="RAM">
            <template #body="{ data }">
              {{ data.ram_usage_percent.toFixed(1) }}%
            </template>
          </Column>
          <Column field="disk_usage_percent" header="Disco">
            <template #body="{ data }">
              {{ data.disk_usage_percent.toFixed(1) }}%
            </template>
          </Column>
          <Column field="uptime_seconds" header="Uptime">
            <template #body="{ data }">
              {{ formatUptime(data.uptime_seconds) }}
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-detail {
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.header-spacer {
  flex: 1;
}

.page-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 4rem;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
}

.card h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

.card.full-width {
  grid-column: 1 / -1;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 1rem;
}

.metric-block .metric-label {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  margin-bottom: 0.4rem;
}

.metric-block .metric-value {
  font-size: 1.3rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.info-table {
  width: 100%;
  border-collapse: collapse;
}

.info-table td {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 0.9rem;
}

.info-table td:first-child {
  width: 35%;
  font-size: 0.85rem;
}

.info-table tr:last-child td {
  border-bottom: none;
}

.mono {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.8rem;
}

.ssh-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.ssh-toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.ssh-host {
  min-width: 180px;
  flex: 1;
}

.ssh-port {
  width: 110px;
}

.ssh-user {
  width: 150px;
}

.ssh-password {
  width: 180px;
}

.ssh-terminal {
  min-height: 300px;
  max-height: 460px;
  overflow: auto;
  margin: 0;
  padding: 1rem;
  border-radius: 8px;
  background: #0b1020;
  color: #d7e1ff;
  border: 1px solid var(--p-content-border-color);
  white-space: pre-wrap;
}

.ssh-input-row {
  display: flex;
  gap: 0.5rem;
}

.script-runner {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.script-toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.language-select {
  width: 160px;
}

.timeout-input {
  width: 140px;
}

.script-editor {
  width: 100%;
}

.script-editor :deep(textarea) {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.85rem;
}

.execution-output {
  max-height: 180px;
  overflow: auto;
}

.execution-output pre {
  margin: 0;
  white-space: pre-wrap;
}

.execution-output .stderr {
  color: var(--p-red-500);
  margin-top: 0.5rem;
}

@media (max-width: 768px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .script-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .ssh-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .language-select,
  .timeout-input,
  .ssh-host,
  .ssh-port,
  .ssh-user,
  .ssh-password {
    width: 100%;
  }
}
</style>
