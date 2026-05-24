<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
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
import ConfirmDialog from 'primevue/confirmdialog'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import InputNumber from 'primevue/inputnumber'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'

import SshTerminal from '@/components/SshTerminal.vue'
import MeshCentralPanel from '@/components/MeshCentralPanel.vue'

const props = defineProps({
  id: { type: String, required: true }
})

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()

const agent = ref(null)
const heartbeats = ref([])
const executions = ref([])
const loading = ref(true)
const deleting = ref(false)
const executing = ref(false)
const refreshInterval = ref(null)
const activeAccessTab = ref('0')

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
const isWindows = computed(() => agent.value?.os === 'windows')
const hasRemoteAccess = computed(() => !!agent.value?.remote_access_url)
const hasSSH = computed(() => !isWindows.value)

const osIcon = computed(() => {
  const os = agent.value?.os
  if (os === 'windows') return 'pi-microsoft'
  if (os === 'darwin') return 'pi-apple'
  return 'pi-server'
})

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
  } catch (err) {
    if (err.response?.status === 404) {
      toast.add({ severity: 'error', summary: 'Não encontrado', detail: 'Agente não existe', life: 3000 })
      router.push('/dashboard')
    } else {
      toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar dados', life: 4000 })
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

async function runScript() {
  if (!scriptForm.value.script.trim()) {
    toast.add({ severity: 'warn', summary: 'Script vazio', detail: 'Digite um script para executar', life: 3000 })
    return
  }
  executing.value = true
  try {
    await agentsApi.createExecution(props.id, {
      language: scriptForm.value.language,
      script: scriptForm.value.script,
      timeout_seconds: scriptForm.value.timeout_seconds
    })
    toast.add({ severity: 'success', summary: 'Execução criada', detail: 'Comando enviado ao agente', life: 3000 })
    await loadData()
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao executar', life: 4000 })
  } finally {
    executing.value = false
  }
}

function handleDelete() {
  if (!agent.value) return
  confirm.require({
    message: `Tem certeza que deseja apagar "${agent.value.hostname}"?\n\nEsta ação vai remover o histórico de heartbeats e o token de instalação. Não pode ser desfeita.`,
    header: 'Confirmar exclusão',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    acceptLabel: 'Sim, apagar',
    rejectLabel: 'Cancelar',
    accept: async () => {
      deleting.value = true
      try {
        await agentsApi.delete(props.id)
        toast.add({ severity: 'success', summary: 'Agente apagado', detail: `"${agent.value.hostname}" removido`, life: 3000 })
        if (refreshInterval.value) clearInterval(refreshInterval.value)
        router.push('/dashboard')
      } catch (err) {
        deleting.value = false
        toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao apagar', life: 4000 })
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
})
</script>

<template>
  <div class="agent-detail">

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <ProgressSpinner style="width: 36px; height: 36px" stroke-width="3" />
      <span class="text-muted">Carregando agente...</span>
    </div>

    <template v-else-if="agent">

      <!-- Header -->
      <div class="page-header">
        <Button icon="pi pi-arrow-left" text rounded @click="router.push('/dashboard')" aria-label="Voltar" />
        <div class="header-identity">
          <i :class="['pi', osIcon, 'os-icon']" />
          <div>
            <h2 class="hostname">{{ agent.hostname }}</h2>
            <span class="platform-label text-muted">{{ agent.platform || agent.os || '—' }}</span>
          </div>
        </div>
        <Tag
          :value="agent.is_online ? 'Online' : 'Offline'"
          :severity="agent.is_online ? 'success' : 'secondary'"
        />
        <div class="header-spacer" />
        <span class="agent-version text-muted" v-if="agent.agent_version">v{{ agent.agent_version }}</span>
        <Button
          label="Apagar"
          icon="pi pi-trash"
          severity="danger"
          text
          :loading="deleting"
          @click="handleDelete"
        />
      </div>

      <ConfirmDialog />

      <!-- Metrics bar -->
      <div class="metrics-bar" v-if="lastHeartbeat">
        <div class="metric-card">
          <div class="metric-icon"><i class="pi pi-microchip" /></div>
          <div class="metric-content">
            <span class="metric-val">{{ lastHeartbeat.cpu_usage_percent.toFixed(1) }}%</span>
            <span class="metric-label">CPU</span>
            <div class="usage-bar">
              <div
                class="usage-fill"
                :class="usageColorClass(lastHeartbeat.cpu_usage_percent)"
                :style="{ width: lastHeartbeat.cpu_usage_percent + '%' }"
              />
            </div>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon"><i class="pi pi-database" /></div>
          <div class="metric-content">
            <span class="metric-val">{{ lastHeartbeat.ram_usage_percent.toFixed(1) }}%</span>
            <span class="metric-label">RAM</span>
            <div class="usage-bar">
              <div
                class="usage-fill"
                :class="usageColorClass(lastHeartbeat.ram_usage_percent)"
                :style="{ width: lastHeartbeat.ram_usage_percent + '%' }"
              />
            </div>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon"><i class="pi pi-hdd" /></div>
          <div class="metric-content">
            <span class="metric-val">{{ lastHeartbeat.disk_usage_percent.toFixed(1) }}%</span>
            <span class="metric-label">Disco</span>
            <div class="usage-bar">
              <div
                class="usage-fill"
                :class="usageColorClass(lastHeartbeat.disk_usage_percent)"
                :style="{ width: lastHeartbeat.disk_usage_percent + '%' }"
              />
            </div>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon"><i class="pi pi-clock" /></div>
          <div class="metric-content">
            <span class="metric-val">{{ formatUptime(lastHeartbeat.uptime_seconds) }}</span>
            <span class="metric-label">Uptime</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon"><i class="pi pi-desktop" /></div>
          <div class="metric-content">
            <span class="metric-val">{{ agent.cpu_cores ?? '—' }}</span>
            <span class="metric-label">Cores</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon"><i class="pi pi-bookmark" /></div>
          <div class="metric-content">
            <span class="metric-val">{{ formatBytes(agent.ram_total_bytes) }}</span>
            <span class="metric-label">RAM Total</span>
          </div>
        </div>
      </div>

      <!-- No heartbeat yet -->
      <div v-else class="no-metrics-banner text-muted">
        <i class="pi pi-info-circle" />
        Aguardando primeiro heartbeat do agente...
      </div>

      <!-- Main grid -->
      <div class="main-grid">

        <!-- System info -->
        <div class="card info-card">
          <div class="card-header">
            <i class="pi pi-info-circle" />
            <h3>Informações do sistema</h3>
          </div>
          <table class="info-table">
            <tbody>
              <tr>
                <td>Sistema</td>
                <td>{{ agent.platform || '—' }}</td>
              </tr>
              <tr>
                <td>SO</td>
                <td>{{ agent.os || '—' }}</td>
              </tr>
              <tr>
                <td>CPU</td>
                <td>{{ agent.cpu_model || '—' }}</td>
              </tr>
              <tr>
                <td>RAM</td>
                <td>{{ formatBytes(agent.ram_total_bytes) }}</td>
              </tr>
              <tr>
                <td>Disco</td>
                <td>{{ formatBytes(agent.disk_total_bytes) }}</td>
              </tr>
              <tr>
                <td>Versão agente</td>
                <td class="mono">{{ agent.agent_version || '—' }}</td>
              </tr>
              <tr>
                <td>Primeira conexão</td>
                <td>{{ formatDateTime(agent.first_seen) }}</td>
              </tr>
              <tr>
                <td>Última conexão</td>
                <td>{{ formatRelativeDate(agent.last_seen) }}</td>
              </tr>
              <tr class="last-row">
                <td>ID</td>
                <td class="mono id-cell" :title="agent.id">{{ agent.id }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Script execution -->
        <div class="card script-card">
          <div class="card-header">
            <i class="pi pi-code" />
            <h3>Execução remota</h3>
          </div>
          <div class="script-runner">
            <div class="script-toolbar">
              <Select
                v-model="scriptForm.language"
                :options="scriptLanguages"
                option-label="label"
                option-value="value"
                class="lang-select"
              />
              <InputNumber
                v-model="scriptForm.timeout_seconds"
                :min="1"
                :max="3600"
                suffix="s"
                show-buttons
                class="timeout-input"
              />
              <Button label="Executar" icon="pi pi-play" :loading="executing" @click="runScript" />
            </div>
            <Textarea
              v-model="scriptForm.script"
              rows="6"
              auto-resize
              class="script-editor mono"
            />
          </div>
        </div>

        <!-- Remote access — tabs -->
        <div class="card access-card full-width">
          <div class="card-header">
            <i class="pi pi-plug" />
            <h3>Acesso Remoto</h3>
          </div>

          <Tabs v-model:value="activeAccessTab">
            <TabList>
              <Tab v-if="hasSSH" value="0">
                <i class="pi pi-terminal tab-icon" />
                Terminal SSH
              </Tab>
              <Tab v-if="hasRemoteAccess" value="1">
                <i class="pi pi-desktop tab-icon" />
                Remote Desktop
              </Tab>
            </TabList>
            <TabPanels>
              <TabPanel v-if="hasSSH" value="0">
                <SshTerminal :agent-id="agent.id" :hostname="agent.hostname" />
              </TabPanel>
              <TabPanel v-if="hasRemoteAccess" value="1">
                <MeshCentralPanel :url="agent.remote_access_url" :agent-name="agent.hostname" />
              </TabPanel>
            </TabPanels>
          </Tabs>

          <!-- Windows with no MeshCentral -->
          <div v-if="isWindows && !hasRemoteAccess" class="no-access-notice">
            <i class="pi pi-info-circle" />
            <div>
              <strong>Remote Desktop não configurado</strong>
              <p class="text-muted">
                Defina <code>MESHCENTRAL_PUBLIC_URL</code> no <code>deploy/.env</code> e instale o
                agente MeshCentral no host para habilitar acesso remoto Windows.
              </p>
            </div>
          </div>
        </div>

        <!-- Execution history -->
        <div class="card full-width">
          <div class="card-header">
            <i class="pi pi-history" />
            <h3>Histórico de execuções</h3>
          </div>
          <DataTable :value="executions" :rows="20" striped-rows>
            <template #empty>
              <div class="table-empty">Nenhuma execução registrada ainda.</div>
            </template>
            <Column field="created_at" header="Criado em" style="width: 190px">
              <template #body="{ data }">{{ formatDateTime(data.created_at) }}</template>
            </Column>
            <Column field="language" header="Tipo" style="width: 120px">
              <template #body="{ data }"><code class="mono">{{ data.language }}</code></template>
            </Column>
            <Column field="status" header="Status" style="width: 130px">
              <template #body="{ data }">
                <Tag :value="data.status" :severity="executionSeverity(data.status)" />
              </template>
            </Column>
            <Column field="exit_code" header="Exit" style="width: 80px">
              <template #body="{ data }">{{ data.exit_code ?? '—' }}</template>
            </Column>
            <Column header="Saída">
              <template #body="{ data }">
                <div class="exec-output">
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

        <!-- Heartbeat history -->
        <div class="card full-width">
          <div class="card-header">
            <i class="pi pi-chart-line" />
            <h3>Histórico de heartbeats</h3>
          </div>
          <DataTable :value="heartbeats" :rows="20" striped-rows>
            <template #empty>
              <div class="table-empty">Nenhum heartbeat recebido ainda.</div>
            </template>
            <Column field="received_at" header="Recebido em" style="width: 200px">
              <template #body="{ data }">{{ formatDateTime(data.received_at) }}</template>
            </Column>
            <Column field="cpu_usage_percent" header="CPU" style="width: 100px">
              <template #body="{ data }">{{ data.cpu_usage_percent.toFixed(1) }}%</template>
            </Column>
            <Column field="ram_usage_percent" header="RAM" style="width: 100px">
              <template #body="{ data }">{{ data.ram_usage_percent.toFixed(1) }}%</template>
            </Column>
            <Column field="disk_usage_percent" header="Disco" style="width: 100px">
              <template #body="{ data }">{{ data.disk_usage_percent.toFixed(1) }}%</template>
            </Column>
            <Column field="uptime_seconds" header="Uptime">
              <template #body="{ data }">{{ formatUptime(data.uptime_seconds) }}</template>
            </Column>
          </DataTable>
        </div>

      </div>
    </template>

  </div>
</template>

<style scoped>
.agent-detail {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem;
  gap: 1rem;
}

/* Header */
.page-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-identity {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.os-icon {
  font-size: 1.5rem;
  color: var(--p-text-muted-color);
}

.hostname {
  font-size: 1.4rem;
  font-weight: 700;
  line-height: 1.2;
  margin: 0;
}

.platform-label {
  font-size: 0.8rem;
}

.header-spacer { flex: 1; }

.agent-version {
  font-size: 0.8rem;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
}

/* Metrics bar */
.metrics-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.75rem;
}

.metric-card {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  padding: 0.875rem 1rem;
}

.metric-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--p-primary-50, rgba(99,102,241,0.08));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-primary-color);
  flex-shrink: 0;
  font-size: 0.9rem;
}

.metric-content {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 0;
}

.metric-val {
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.metric-label {
  font-size: 0.7rem;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.usage-bar {
  height: 3px;
  background: var(--p-content-border-color);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 0.35rem;
}

.usage-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--p-green-500);
  transition: width 0.4s ease;
}

.usage-fill.warn   { background: var(--p-yellow-500); }
.usage-fill.danger { background: var(--p-red-500); }

.no-metrics-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  font-size: 0.875rem;
}

/* Main grid */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
}

.full-width {
  grid-column: 1 / -1;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.card-header i {
  color: var(--p-text-muted-color);
}

.card-header h3 {
  font-size: 0.9rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
  margin: 0;
}

/* Info table */
.info-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.info-table td {
  padding: 0.45rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
  vertical-align: middle;
}

.info-table td:first-child {
  width: 38%;
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
}

.info-table tr.last-row td {
  border-bottom: none;
}

.id-cell {
  font-size: 0.7rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
  display: block;
}

/* Script runner */
.script-runner {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.script-toolbar {
  display: flex;
  gap: 0.625rem;
  align-items: center;
}

.lang-select { width: 150px; }
.timeout-input { width: 130px; }

.script-editor { width: 100%; }
.script-editor :deep(textarea) {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.82rem;
}

/* Access tabs */
.tab-icon {
  margin-right: 0.4rem;
  font-size: 0.875rem;
}

.no-access-notice {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 1rem;
  background: var(--p-surface-100, rgba(255,255,255,0.04));
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
}

.no-access-notice i {
  color: var(--p-text-muted-color);
  margin-top: 0.1rem;
  flex-shrink: 0;
}

.no-access-notice p {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
}

/* Execution output */
.exec-output {
  max-height: 160px;
  overflow: auto;
}

.exec-output pre {
  margin: 0;
  white-space: pre-wrap;
  font-size: 0.8rem;
}

.exec-output .stderr {
  color: var(--p-red-500);
  margin-top: 0.25rem;
}

.table-empty {
  padding: 2rem;
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

/* Shared */
.mono {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.8rem;
}

/* Responsive */
@media (max-width: 768px) {
  .main-grid {
    grid-template-columns: 1fr;
  }

  .metrics-bar {
    grid-template-columns: repeat(2, 1fr);
  }

  .script-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .lang-select, .timeout-input {
    width: 100%;
  }
}
</style>
