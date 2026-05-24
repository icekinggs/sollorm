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
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'

import SshTerminal from '@/components/SshTerminal.vue'
import RemoteScreenPanel from '@/components/RemoteScreenPanel.vue'
import PatchManager from '@/components/PatchManager.vue'

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
const refreshInterval = ref(null)
const activeTab = ref('access')

const lastHeartbeat = computed(() => heartbeats.value[0] || null)
const isWindows = computed(() => agent.value?.os === 'windows')
const hasSSH    = computed(() => !isWindows.value)
const activeRemoteTab = ref('0')

const osIcon = computed(() => {
  const os = agent.value?.os
  if (os === 'windows') return 'pi-microsoft'
  if (os === 'darwin') return 'pi-apple'
  return 'pi-server'
})

const osLabel = computed(() => {
  const os = agent.value?.os
  if (os === 'windows') return 'Windows'
  if (os === 'darwin') return 'macOS'
  return 'Linux'
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

function handleDelete() {
  if (!agent.value) return
  confirm.require({
    message: `Tem certeza que deseja apagar "${agent.value.hostname}"? Esta ação não pode ser desfeita.`,
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

    <div v-if="loading" class="loading-state">
      <ProgressSpinner style="width: 36px; height: 36px" stroke-width="3" />
    </div>

    <template v-else-if="agent">
      <ConfirmDialog />

      <!-- ── Header ── -->
      <div class="page-header">
        <Button icon="pi pi-arrow-left" text rounded @click="router.push('/dashboard')" />
        <i :class="['pi', osIcon, 'os-icon']" />
        <div class="header-title">
          <h2>{{ agent.hostname }}</h2>
          <span class="subtitle">{{ osLabel }} · {{ agent.platform || agent.os }}</span>
        </div>
        <Tag
          :value="agent.is_online ? 'Online' : 'Offline'"
          :severity="agent.is_online ? 'success' : 'secondary'"
          class="status-tag"
        />
        <div class="spacer" />
        <span class="version-badge" v-if="agent.agent_version">v{{ agent.agent_version }}</span>
        <Button icon="pi pi-trash" text rounded severity="danger" :loading="deleting" @click="handleDelete" />
      </div>

      <!-- ── Metrics strip ── -->
      <div class="metrics-strip" v-if="lastHeartbeat">
        <div class="metric">
          <div class="metric-top">
            <span class="metric-val" :class="usageColorClass(lastHeartbeat.cpu_usage_percent)">
              {{ lastHeartbeat.cpu_usage_percent.toFixed(1) }}%
            </span>
            <span class="metric-name">CPU</span>
          </div>
          <div class="bar-track"><div class="bar-fill" :class="usageColorClass(lastHeartbeat.cpu_usage_percent)" :style="{ width: lastHeartbeat.cpu_usage_percent + '%' }" /></div>
        </div>
        <div class="metric-divider" />
        <div class="metric">
          <div class="metric-top">
            <span class="metric-val" :class="usageColorClass(lastHeartbeat.ram_usage_percent)">
              {{ lastHeartbeat.ram_usage_percent.toFixed(1) }}%
            </span>
            <span class="metric-name">RAM</span>
          </div>
          <div class="bar-track"><div class="bar-fill" :class="usageColorClass(lastHeartbeat.ram_usage_percent)" :style="{ width: lastHeartbeat.ram_usage_percent + '%' }" /></div>
        </div>
        <div class="metric-divider" />
        <div class="metric">
          <div class="metric-top">
            <span class="metric-val" :class="usageColorClass(lastHeartbeat.disk_usage_percent)">
              {{ lastHeartbeat.disk_usage_percent.toFixed(1) }}%
            </span>
            <span class="metric-name">Disco</span>
          </div>
          <div class="bar-track"><div class="bar-fill" :class="usageColorClass(lastHeartbeat.disk_usage_percent)" :style="{ width: lastHeartbeat.disk_usage_percent + '%' }" /></div>
        </div>
        <div class="metric-divider" />
        <div class="metric flat">
          <span class="metric-val">{{ formatUptime(lastHeartbeat.uptime_seconds) }}</span>
          <span class="metric-name">Uptime</span>
        </div>
        <div class="metric-divider" />
        <div class="metric flat">
          <span class="metric-val">{{ agent.cpu_cores ?? '—' }}</span>
          <span class="metric-name">Cores</span>
        </div>
        <div class="metric-divider" />
        <div class="metric flat">
          <span class="metric-val">{{ formatBytes(agent.ram_total_bytes) }}</span>
          <span class="metric-name">RAM Total</span>
        </div>
        <div class="metric-divider" />
        <div class="metric flat">
          <span class="metric-val">{{ formatBytes(agent.disk_total_bytes) }}</span>
          <span class="metric-name">Disco Total</span>
        </div>
      </div>
      <div v-else class="no-heartbeat">
        <i class="pi pi-info-circle" /> Aguardando primeiro heartbeat...
      </div>

      <!-- ── Body: sidebar + tabs ── -->
      <div class="body-layout">

        <!-- Sidebar -->
        <aside class="sidebar">
          <p class="sidebar-section">Sistema</p>
          <div class="info-row"><span class="info-key">SO</span><span class="info-val">{{ agent.platform || '—' }}</span></div>
          <div class="info-row"><span class="info-key">CPU</span><span class="info-val">{{ agent.cpu_model || '—' }}</span></div>
          <div class="info-row"><span class="info-key">Disco</span><span class="info-val">{{ formatBytes(agent.disk_total_bytes) }}</span></div>
          <div class="info-row"><span class="info-key">Versão</span><span class="info-val mono">{{ agent.agent_version || '—' }}</span></div>

          <p class="sidebar-section mt">Conexão</p>
          <div class="info-row"><span class="info-key">Token</span><span class="info-val mono">{{ agent.token_prefix ? agent.token_prefix + '…' : '—' }}</span></div>
          <div class="info-row"><span class="info-key">1ª conexão</span><span class="info-val">{{ formatDateTime(agent.first_seen) }}</span></div>
          <div class="info-row"><span class="info-key">Último acesso</span><span class="info-val">{{ formatRelativeDate(agent.last_seen) }}</span></div>

          <p class="sidebar-section mt">ID</p>
          <span class="agent-id mono" :title="agent.id">{{ agent.id }}</span>
        </aside>

        <!-- Main tabs -->
        <div class="main-content">
          <Tabs v-model:value="activeTab">
            <TabList>
              <Tab value="access">
                <i class="pi pi-plug tab-icon" />Acesso Remoto
              </Tab>
              <Tab value="patches">
                <i class="pi pi-shield tab-icon" />Patches
              </Tab>
              <Tab value="executions">
                <i class="pi pi-history tab-icon" />Execuções
                <span v-if="executions.length" class="tab-badge">{{ executions.length }}</span>
              </Tab>
            </TabList>

            <TabPanels>

              <!-- Acesso remoto -->
              <TabPanel value="access">
                <Tabs v-model:value="activeRemoteTab">
                  <TabList>
                    <Tab v-if="hasSSH"    value="0"><i class="pi pi-terminal tab-icon" />SSH</Tab>
                    <Tab v-if="isWindows" value="1"><i class="pi pi-desktop tab-icon" />Remote Desktop</Tab>
                  </TabList>
                  <TabPanels>
                    <TabPanel v-if="hasSSH"    value="0">
                      <SshTerminal :agent-id="agent.id" :hostname="agent.hostname" />
                    </TabPanel>
                    <TabPanel v-if="isWindows" value="1">
                      <RemoteScreenPanel :agent-id="agent.id" />
                    </TabPanel>
                  </TabPanels>
                </Tabs>
              </TabPanel>

              <!-- Patches -->
              <TabPanel value="patches">
                <PatchManager :agent-id="agent.id" />
              </TabPanel>

              <!-- Execuções -->
              <TabPanel value="executions">
                <DataTable :value="executions" :rows="20" striped-rows>
                  <template #empty>
                    <div class="empty-state">Nenhuma execução registrada ainda.</div>
                  </template>
                  <Column field="created_at" header="Data" style="width: 180px">
                    <template #body="{ data }">{{ formatDateTime(data.created_at) }}</template>
                  </Column>
                  <Column field="language" header="Tipo" style="width: 110px">
                    <template #body="{ data }"><code class="mono">{{ data.language }}</code></template>
                  </Column>
                  <Column field="status" header="Status" style="width: 130px">
                    <template #body="{ data }">
                      <Tag :value="data.status" :severity="executionSeverity(data.status)" />
                    </template>
                  </Column>
                  <Column field="exit_code" header="Exit" style="width: 70px">
                    <template #body="{ data }">{{ data.exit_code ?? '—' }}</template>
                  </Column>
                  <Column header="Saída">
                    <template #body="{ data }">
                      <div class="exec-output">
                        <pre v-if="data.stdout" class="mono">{{ data.stdout }}</pre>
                        <pre v-if="data.stderr" class="mono err">{{ data.stderr }}</pre>
                        <span v-if="!data.stdout && !data.stderr" class="muted">{{ data.error_message || '—' }}</span>
                      </div>
                    </template>
                  </Column>
                </DataTable>
              </TabPanel>

            </TabPanels>
          </Tabs>
        </div>

      </div>
    </template>
  </div>
</template>

<style scoped>
.agent-detail {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Loading */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6rem;
}

/* Header */
.page-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.os-icon {
  font-size: 1.6rem;
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.header-title h2 {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0;
  line-height: 1.2;
}

.header-title .subtitle {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
}

.status-tag { flex-shrink: 0; }

.spacer { flex: 1; }

.version-badge {
  font-size: 0.75rem;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  color: var(--p-text-muted-color);
  background: var(--p-content-border-color);
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
}

/* Metrics strip */
.metrics-strip {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  padding: 0.875rem 1.25rem;
  flex-wrap: wrap;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 72px;
}

.metric-top {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
}

.metric-val {
  font-size: 1rem;
  font-weight: 700;
  line-height: 1;
}

.metric-val.warn   { color: var(--p-yellow-500); }
.metric-val.danger { color: var(--p-red-500); }

.metric-name {
  font-size: 0.7rem;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric.flat .metric-val { font-size: 0.9rem; }
.metric.flat { flex-direction: row; align-items: baseline; gap: 0.4rem; }

.bar-track {
  height: 3px;
  background: var(--p-content-border-color);
  border-radius: 2px;
  overflow: hidden;
  width: 100%;
}

.bar-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--p-green-500);
  transition: width 0.4s ease;
}

.bar-fill.warn   { background: var(--p-yellow-500); }
.bar-fill.danger { background: var(--p-red-500); }

.metric-divider {
  width: 1px;
  height: 28px;
  background: var(--p-content-border-color);
  flex-shrink: 0;
}

.no-heartbeat {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

/* Body layout */
.body-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 1rem;
  align-items: start;
}

/* Sidebar */
.sidebar {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  padding: 1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.sidebar-section {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--p-text-muted-color);
  margin: 0 0 0.5rem;
}

.sidebar-section.mt { margin-top: 1rem; }

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.3rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 0.8rem;
}

.info-row:last-of-type { border-bottom: none; }

.info-key {
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.info-val {
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 130px;
}

.agent-id {
  font-size: 0.65rem;
  color: var(--p-text-muted-color);
  word-break: break-all;
  line-height: 1.4;
  margin-top: 0.25rem;
}

/* Main content */
.main-content {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  overflow: hidden;
}

.main-content :deep(.p-tabs) { background: transparent; }
.main-content :deep(.p-tabpanels) { padding: 1.25rem 1.5rem; }

/* Tab badges */
.tab-icon { margin-right: 0.35rem; font-size: 0.85rem; }
.tab-badge {
  margin-left: 0.4rem;
  background: var(--p-content-border-color);
  color: var(--p-text-muted-color);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
}

/* Notice */
.notice {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  padding: 1rem;
  background: var(--p-surface-100, rgba(255,255,255,0.03));
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  margin-top: 0.75rem;
  font-size: 0.875rem;
}

.notice i { color: var(--p-text-muted-color); margin-top: 0.15rem; flex-shrink: 0; }
.notice p { margin: 0.3rem 0 0; font-size: 0.82rem; color: var(--p-text-muted-color); }

/* Executions table */
.exec-output {
  max-height: 140px;
  overflow: auto;
}

.exec-output pre {
  margin: 0;
  white-space: pre-wrap;
  font-size: 0.78rem;
}

.exec-output .err { color: var(--p-red-400); margin-top: 0.2rem; }

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

/* Shared */
.mono { font-family: 'SF Mono', Monaco, Consolas, monospace; font-size: 0.8rem; }
.muted { color: var(--p-text-muted-color); }

/* Responsive */
@media (max-width: 900px) {
  .body-layout {
    grid-template-columns: 1fr;
  }

  .metrics-strip {
    gap: 0.75rem;
  }

  .metric-divider { display: none; }
}
</style>
