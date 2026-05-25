<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { agentsApi } from '@/api/agents'
import { groupsApi } from '@/api/groups'
import { alertsApi } from '@/api/alerts'
import { softwareApi } from '@/api/software'
import {
  formatBytes,
  formatRelativeDate,
  formatDateTime,
  formatUptime,
  usageColorClass
} from '@/composables/useFormatters'

import InputText from 'primevue/inputtext'
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
import Select from 'primevue/select'

import { useNotifications } from '@/composables/useNotifications'
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
const groups = ref([])
const agentAlerts = ref([])
const softwareItems = ref([])
const softwareFilter = ref('')
const loading = ref(true)
const deleting = ref(false)
const assigningGroup = ref(false)
const updating = ref(false)
const activeTab = ref('access')

const agentFiringAlerts = computed(() => agentAlerts.value.filter(e => e.state === 'firing'))
const agentAlertHistory  = computed(() => agentAlerts.value.filter(e => e.state === 'resolved').slice(0, 30))

const filteredSoftware = computed(() => {
  const q = softwareFilter.value.trim().toLowerCase()
  if (!q) return softwareItems.value
  return softwareItems.value.filter(s => s.name.toLowerCase().includes(q) || (s.publisher || '').toLowerCase().includes(q))
})

const softwareLastSync = computed(() => {
  if (!softwareItems.value.length) return null
  return softwareItems.value[0].collected_at
})

function metricLabel(m) {
  return { cpu_usage_percent: 'CPU', ram_usage_percent: 'RAM', disk_usage_percent: 'Disco' }[m] || m
}

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

const groupOptions = computed(() => [
  { label: 'Sem grupo', value: null },
  ...groups.value.map(g => ({ label: g.name, value: g.id, color: g.color }))
])

async function loadData() {
  try {
    const [agentRes, hbRes, execRes, grpRes, alertRes] = await Promise.all([
      agentsApi.get(props.id),
      agentsApi.heartbeats(props.id, 20),
      agentsApi.executions(props.id, 20),
      groupsApi.list(),
      alertsApi.listAgentEvents(props.id, { limit: 50 }),
    ])
    agent.value = agentRes.data
    heartbeats.value = hbRes.data
    executions.value = execRes.data
    groups.value = grpRes.data
    agentAlerts.value = alertRes.data

    softwareApi.list(props.id).then(r => { softwareItems.value = r.data }).catch(() => {})
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

async function assignGroup(groupId) {
  if (!agent.value) return
  assigningGroup.value = true
  try {
    const res = await groupsApi.assignAgent(props.id, groupId)
    agent.value.group_id = res.data.group_id
    agent.value.group_name = res.data.group_name
    toast.add({ severity: 'success', summary: 'Grupo atualizado', detail: res.data.group_name || 'Sem grupo', life: 2000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao atualizar grupo', life: 4000 })
  } finally {
    assigningGroup.value = false
  }
}

async function triggerUpdate() {
  updating.value = true
  try {
    await agentsApi.update(props.id)
    toast.add({ severity: 'info', summary: 'Atualização iniciada', detail: 'O agente vai reiniciar após o download', life: 5000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao iniciar atualização', life: 4000 })
    updating.value = false
  }
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
        router.push('/dashboard')
      } catch (err) {
        deleting.value = false
        toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao apagar', life: 4000 })
      }
    }
  })
}

useNotifications((msg) => {
  if (msg.agent_id !== props.id) return

  if (msg.type === 'agent_online' && agent.value) {
    agent.value.is_online = true
    agent.value.last_seen = new Date().toISOString()
  } else if (msg.type === 'agent_offline' && agent.value) {
    agent.value.is_online = false
  } else if (msg.type === 'agent_heartbeat' && agent.value) {
    agent.value.is_online            = true
    agent.value.last_seen            = msg.last_seen
    agent.value.hostname             = msg.hostname ?? agent.value.hostname
    // Prepend new heartbeat to history (keep last 20)
    heartbeats.value = [
      {
        cpu_usage_percent:  msg.cpu_usage_percent,
        ram_usage_percent:  msg.ram_usage_percent,
        disk_usage_percent: msg.disk_usage_percent,
        uptime_seconds:     msg.uptime_seconds,
        reported_at:        msg.last_seen,
      },
      ...heartbeats.value,
    ].slice(0, 20)
  } else if (msg.type === 'alert_fired') {
    agentAlerts.value.unshift({
      id: msg.event_id, rule_id: msg.rule_id, rule_name: msg.rule_name,
      agent_id: msg.agent_id, metric: msg.metric, value: msg.value,
      threshold: msg.threshold, operator: msg.operator, severity: msg.severity,
      state: 'firing', fired_at: msg.fired_at, resolved_at: null,
    })
    toast.add({ severity: msg.severity === 'critical' ? 'error' : 'warn', summary: msg.rule_name, detail: `${metricLabel(msg.metric)} ${msg.operator} ${msg.threshold}%`, life: 5000 })
  } else if (msg.type === 'alert_resolved') {
    const ev = agentAlerts.value.find(e => e.id === msg.event_id)
    if (ev) { ev.state = 'resolved'; ev.resolved_at = msg.resolved_at }
  } else if (msg.type === 'update_progress' && msg.agent_id === props.id) {
    if (msg.status === 'restarting') {
      updating.value = false
      if (agent.value) agent.value.update_available = false
      toast.add({ severity: 'success', summary: 'Agente atualizado', detail: `v${msg.version} instalado — reiniciando`, life: 6000 })
    } else if (msg.status === 'failed') {
      updating.value = false
      toast.add({ severity: 'error', summary: 'Falha na atualização', detail: msg.error || 'Erro desconhecido', life: 6000 })
    }
  }
})

onMounted(() => { loadData() })
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
        <Select
          :model-value="agent.group_id"
          :options="groupOptions"
          option-label="label"
          option-value="value"
          placeholder="Sem grupo"
          :loading="assigningGroup"
          class="group-select"
          @change="assignGroup($event.value)"
        />
        <span class="version-badge" v-if="agent.agent_version">v{{ agent.agent_version }}</span>
        <Button
          v-if="agent.update_available"
          icon="pi pi-arrow-circle-up"
          label="Atualizar"
          severity="warn"
          size="small"
          :loading="updating"
          @click="triggerUpdate"
          v-tooltip.left="'Nova versão disponível'"
        />
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
              <Tab value="alerts">
                <i class="pi pi-bell tab-icon" />Alertas
                <span v-if="agentFiringAlerts.length" class="tab-badge alert-tab-badge">{{ agentFiringAlerts.length }}</span>
              </Tab>
              <Tab value="software">
                <i class="pi pi-box tab-icon" />Software
                <span v-if="softwareItems.length" class="tab-badge">{{ softwareItems.length }}</span>
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

              <!-- Alertas -->
              <TabPanel value="alerts">
                <div class="alerts-tab">
                  <div v-if="agentFiringAlerts.length === 0 && agentAlertHistory.length === 0" class="empty-state">
                    Nenhum alerta para este agente.
                  </div>
                  <template v-else>
                    <div v-if="agentFiringAlerts.length" class="alert-section">
                      <div class="alert-section-title">Ativos</div>
                      <div v-for="ev in agentFiringAlerts" :key="ev.id" class="alert-item" :class="ev.severity">
                        <i :class="['pi', ev.severity === 'critical' ? 'pi-times-circle' : 'pi-exclamation-triangle']" />
                        <div class="alert-item-body">
                          <span class="alert-item-rule">{{ ev.rule_name }}</span>
                          <span class="alert-item-desc">{{ metricLabel(ev.metric) }} {{ ev.operator }} {{ ev.threshold }}% — valor: <strong>{{ ev.value?.toFixed(1) }}%</strong></span>
                        </div>
                        <span class="alert-item-time muted">{{ formatRelativeDate(ev.fired_at) }}</span>
                      </div>
                    </div>
                    <div v-if="agentAlertHistory.length" class="alert-section">
                      <div class="alert-section-title">Histórico</div>
                      <div v-for="ev in agentAlertHistory" :key="ev.id" class="alert-item resolved">
                        <i class="pi pi-check-circle" />
                        <div class="alert-item-body">
                          <span class="alert-item-rule">{{ ev.rule_name }}</span>
                          <span class="alert-item-desc">{{ metricLabel(ev.metric) }} {{ ev.operator }} {{ ev.threshold }}%</span>
                        </div>
                        <span class="alert-item-time muted">{{ formatRelativeDate(ev.fired_at) }}</span>
                      </div>
                    </div>
                  </template>
                </div>
              </TabPanel>

              <!-- Software -->
              <TabPanel value="software">
                <div class="software-tab">
                  <div class="software-toolbar">
                    <InputText v-model="softwareFilter" placeholder="Filtrar por nome ou publisher..." class="sw-filter" />
                    <span v-if="softwareLastSync" class="muted sw-sync-time">
                      Atualizado {{ formatRelativeDate(softwareLastSync) }}
                    </span>
                  </div>
                  <DataTable :value="filteredSoftware" :rows="50" paginator striped-rows>
                    <template #empty>
                      <div class="empty-state">
                        {{ softwareItems.length ? 'Nenhum resultado para o filtro.' : 'Nenhum inventário disponível. O agente envia ao iniciar.' }}
                      </div>
                    </template>
                    <Column field="name" header="Nome" sortable />
                    <Column field="version" header="Versão" style="width: 160px" />
                    <Column field="publisher" header="Publisher" style="width: 220px">
                      <template #body="{ data }">{{ data.publisher || '—' }}</template>
                    </Column>
                    <Column field="install_date" header="Data instalação" style="width: 140px">
                      <template #body="{ data }">{{ data.install_date || '—' }}</template>
                    </Column>
                    <Column field="source" header="Fonte" style="width: 110px">
                      <template #body="{ data }">
                        <code class="mono">{{ data.source }}</code>
                      </template>
                    </Column>
                  </DataTable>
                </div>
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

.group-select {
  font-size: 0.82rem;
  width: 160px;
}

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

.alert-tab-badge {
  background: rgba(239, 68, 68, 0.15);
  color: var(--p-red-500);
}

/* Alerts tab */
.alerts-tab { padding: 0.5rem 0; }

.alert-section { margin-bottom: 0.5rem; }

.alert-section-title {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--p-text-muted-color);
  padding: 0.5rem 1.25rem 0.25rem;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 1.25rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.alert-item:last-child { border-bottom: none; }

.alert-item .pi { font-size: 1rem; flex-shrink: 0; }
.alert-item.critical .pi { color: var(--p-red-500); }
.alert-item.warning .pi  { color: var(--p-yellow-500, #f59e0b); }
.alert-item.resolved     { opacity: 0.55; }
.alert-item.resolved .pi { color: var(--p-green-500); }

.alert-item-body { flex: 1; display: flex; flex-direction: column; gap: 0.1rem; }
.alert-item-rule { font-weight: 600; font-size: 0.875rem; }
.alert-item-desc { font-size: 0.78rem; color: var(--p-text-muted-color); }
.alert-item-time { font-size: 0.75rem; white-space: nowrap; }

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

/* Software tab */
.software-tab { padding: 0.5rem 0; }

.software-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.sw-filter { width: 280px; font-size: 0.85rem; }
.sw-sync-time { font-size: 0.78rem; }

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
