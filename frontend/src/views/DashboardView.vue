<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { agentsApi } from '@/api/agents'
import { groupsApi } from '@/api/groups'
import { alertsApi } from '@/api/alerts'
import { formatBytes, formatRelativeDate } from '@/composables/useFormatters'
import { useNotifications } from '@/composables/useNotifications'

import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import InputText from 'primevue/inputtext'

const router = useRouter()
const toast = useToast()

const agents = ref([])
const groups = ref([])
const firingAlerts = ref([]) // active alert events keyed by agent_id
const loading = ref(true)
const refreshing = ref(false)
const lastRefresh = ref(null)
const search = ref('')
const activeGroup = ref(null) // null = todos, 'none' = sem grupo, or group.id

const stats = computed(() => {
  const total = agents.value.length
  const online = agents.value.filter(a => a.is_online).length
  return { total, online, offline: total - online }
})

const onlinePct = computed(() => {
  if (!stats.value.total) return 0
  return Math.round((stats.value.online / stats.value.total) * 100)
})

const filtered = computed(() => {
  let list = agents.value

  if (activeGroup.value === 'none') {
    list = list.filter(a => !a.group_id)
  } else if (activeGroup.value !== null) {
    list = list.filter(a => a.group_id === activeGroup.value)
  }

  const q = search.value.trim().toLowerCase()
  if (!q) return list
  return list.filter(a =>
    a.hostname.toLowerCase().includes(q) ||
    a.platform?.toLowerCase().includes(q) ||
    a.os?.toLowerCase().includes(q)
  )
})

async function load(manual = false) {
  if (manual) refreshing.value = true
  try {
    const [agRes, grpRes, alertRes] = await Promise.all([agentsApi.list(), groupsApi.list(), alertsApi.listEvents({ state: 'firing', limit: 200 })])
    agents.value = agRes.data
    groups.value = grpRes.data
    firingAlerts.value = alertRes.data
    lastRefresh.value = new Date()
    if (manual) toast.add({ severity: 'success', summary: 'Atualizado', detail: `${agRes.data.length} agentes`, life: 2000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao carregar', life: 4000 })
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function groupAgentCount(groupId) {
  return agents.value.filter(a => a.group_id === groupId).length
}

const ungroupedCount = computed(() => agents.value.filter(a => !a.group_id).length)

function agentAlertSeverity(agentId) {
  const evs = firingAlerts.value.filter(e => e.agent_id === agentId)
  if (!evs.length) return null
  return evs.some(e => e.severity === 'critical') ? 'critical' : 'warning'
}

function osIcon(os) {
  if (os === 'windows') return 'pi-microsoft'
  if (os === 'darwin') return 'pi-apple'
  return 'pi-server'
}

useNotifications((msg) => {
  if (msg.type === 'agent_online') {
    const a = agents.value.find(x => x.id === msg.agent_id)
    if (a) { a.is_online = true; a.last_seen = new Date().toISOString() }
  } else if (msg.type === 'agent_offline') {
    const a = agents.value.find(x => x.id === msg.agent_id)
    if (a) a.is_online = false
  } else if (msg.type === 'agent_heartbeat') {
    const a = agents.value.find(x => x.id === msg.agent_id)
    if (a) {
      a.is_online  = true
      a.last_seen  = msg.last_seen
      a.hostname   = msg.hostname ?? a.hostname
    }
  } else if (msg.type === 'alert_fired') {
    firingAlerts.value.push({ id: msg.event_id, rule_id: msg.rule_id, agent_id: msg.agent_id, metric: msg.metric, value: msg.value, threshold: msg.threshold, operator: msg.operator, severity: msg.severity, state: 'firing', fired_at: msg.fired_at })
  } else if (msg.type === 'alert_resolved') {
    firingAlerts.value = firingAlerts.value.filter(e => e.id !== msg.event_id)
  }
})

onMounted(() => { load() })
</script>

<template>
  <div class="dashboard">

    <!-- Header -->
    <div class="dash-header">
      <div>
        <h2>Dashboard</h2>
        <span class="last-refresh" v-if="lastRefresh">
          Atualizado {{ formatRelativeDate(lastRefresh.toISOString()) }}
        </span>
      </div>
      <Button
        icon="pi pi-refresh"
        text
        rounded
        :loading="refreshing"
        @click="load(true)"
        v-tooltip.left="'Atualizar'"
      />
    </div>

    <!-- Stats -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon total"><i class="pi pi-desktop" /></div>
        <div class="stat-body">
          <span class="stat-num">{{ stats.total }}</span>
          <span class="stat-label">Total</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon online"><i class="pi pi-circle-fill" /></div>
        <div class="stat-body">
          <span class="stat-num online">{{ stats.online }}</span>
          <span class="stat-label">Online</span>
        </div>
        <div class="stat-bar-wrap" v-if="stats.total">
          <div class="stat-bar" :style="{ width: onlinePct + '%' }" />
          <span class="stat-pct">{{ onlinePct }}%</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon offline"><i class="pi pi-circle" /></div>
        <div class="stat-body">
          <span class="stat-num offline">{{ stats.offline }}</span>
          <span class="stat-label">Offline</span>
        </div>
      </div>
    </div>

    <!-- Agents panel -->
    <div class="agents-panel">

      <!-- Toolbar -->
      <div class="panel-toolbar">
        <span class="panel-title">Agentes</span>
        <div class="group-filters" v-if="groups.length > 0">
          <button
            class="group-chip"
            :class="{ active: activeGroup === null }"
            @click="activeGroup = null"
          >Todos</button>
          <button
            v-for="g in groups"
            :key="g.id"
            class="group-chip"
            :class="{ active: activeGroup === g.id }"
            :style="activeGroup === g.id ? { background: g.color + '22', color: g.color, borderColor: g.color } : {}"
            @click="activeGroup = g.id"
          >
            <span class="chip-dot" :style="{ background: g.color || '#6366f1' }" />
            {{ g.name }}
          </button>
          <button
            class="group-chip"
            :class="{ active: activeGroup === 'none' }"
            @click="activeGroup = 'none'"
          >Sem grupo</button>
        </div>
        <div class="search-wrap">
          <i class="pi pi-search search-icon" />
          <InputText
            v-model="search"
            placeholder="Filtrar por hostname, SO..."
            class="search-input"
          />
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="state-box">
        <ProgressSpinner style="width:28px;height:28px" stroke-width="3" />
        <span>Carregando...</span>
      </div>

      <!-- Empty -->
      <div v-else-if="agents.length === 0" class="state-box empty">
        <i class="pi pi-desktop" />
        <strong>Nenhum agente registrado</strong>
        <span>Instale o agente em um host para vê-lo aparecer aqui.</span>
      </div>

      <!-- No results -->
      <div v-else-if="filtered.length === 0" class="state-box">
        <i class="pi pi-search" />
        <span>Nenhum agente encontrado para "<strong>{{ search }}</strong>"</span>
      </div>

      <!-- Agent list -->
      <div v-else class="agent-list">

        <!-- List header -->
        <div class="list-head">
          <span style="width:80px">Status</span>
          <span class="col-host">Hostname</span>
          <span class="col-group">Grupo</span>
          <span class="col-os">Sistema</span>
          <span class="col-hw">CPU</span>
          <span class="col-hw">RAM</span>
          <span class="col-hw">Disco</span>
          <span class="col-seen">Visto</span>
          <span style="width:24px" />
        </div>

        <!-- Rows -->
        <div
          v-for="agent in filtered"
          :key="agent.id"
          class="agent-row"
          :class="{ offline: !agent.is_online }"
          @click="router.push({ name: 'agent-detail', params: { id: agent.id } })"
        >
          <!-- Status dot -->
          <div style="width:80px">
            <span class="dot-wrap">
              <span class="dot" :class="agent.is_online ? 'dot-on' : 'dot-off'" />
              <span :class="agent.is_online ? 'on-label' : 'off-label'">
                {{ agent.is_online ? 'Online' : 'Offline' }}
              </span>
            </span>
          </div>

          <!-- Hostname -->
          <div class="col-host">
            <span class="hostname">{{ agent.hostname }}</span>
            <span class="agent-ver" v-if="agent.agent_version">v{{ agent.agent_version }}</span>
            <span v-if="agent.update_available" class="update-badge" title="Atualização disponível">
              <i class="pi pi-arrow-circle-up" />
            </span>
            <span v-if="agentAlertSeverity(agent.id) === 'critical'" class="alert-badge critical" title="Alerta crítico ativo">
              <i class="pi pi-times-circle" />
            </span>
            <span v-else-if="agentAlertSeverity(agent.id) === 'warning'" class="alert-badge warning" title="Aviso ativo">
              <i class="pi pi-exclamation-triangle" />
            </span>
          </div>

          <!-- Group -->
          <div class="col-group">
            <span v-if="agent.group_name" class="group-badge" :style="{ background: (groups.find(g=>g.id===agent.group_id)?.color || '#6366f1') + '22', color: groups.find(g=>g.id===agent.group_id)?.color || '#6366f1' }">
              {{ agent.group_name }}
            </span>
            <span v-else class="no-group">—</span>
          </div>

          <!-- OS -->
          <div class="col-os">
            <i :class="['pi', osIcon(agent.os), 'os-icon']" />
            <span class="os-label">{{ agent.platform || agent.os || '—' }}</span>
          </div>

          <!-- HW -->
          <div class="col-hw hw-val">{{ agent.cpu_cores ? agent.cpu_cores + ' cores' : '—' }}</div>
          <div class="col-hw hw-val">{{ formatBytes(agent.ram_total_bytes) }}</div>
          <div class="col-hw hw-val">{{ formatBytes(agent.disk_total_bytes) }}</div>

          <!-- Last seen -->
          <div class="col-seen hw-val">{{ formatRelativeDate(agent.last_seen) }}</div>

          <!-- Arrow -->
          <i class="pi pi-chevron-right arrow" />
        </div>

      </div>
    </div>

  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Header */
.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dash-header h2 {
  font-size: 1.35rem;
  font-weight: 700;
  margin: 0 0 0.15rem;
}

.last-refresh {
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
}

/* Stats */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.875rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  padding: 1rem 1.25rem;
  position: relative;
  overflow: hidden;
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
}

.stat-icon.total  { background: rgba(99,102,241,0.12); color: var(--p-primary-color); }
.stat-icon.online { background: rgba(34,197,94,0.12);  color: var(--p-green-500); }
.stat-icon.offline{ background: rgba(148,163,184,0.12); color: var(--p-text-muted-color); }

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.stat-num {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1;
}

.stat-num.online  { color: var(--p-green-500); }
.stat-num.offline { color: var(--p-text-muted-color); }

.stat-label {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.stat-bar-wrap {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--p-content-border-color);
  display: flex;
  align-items: center;
}

.stat-bar {
  height: 100%;
  background: var(--p-green-500);
  transition: width 0.5s ease;
}

.stat-pct {
  position: absolute;
  right: 0.75rem;
  bottom: 6px;
  font-size: 0.65rem;
  color: var(--p-text-muted-color);
}

/* Agents panel */
.agents-panel {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  overflow: hidden;
}

.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1.25rem;
  border-bottom: 1px solid var(--p-content-border-color);
  gap: 1rem;
}

.panel-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.group-filters {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
  flex-wrap: wrap;
}

.group-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  border: 1px solid var(--p-content-border-color);
  background: transparent;
  color: var(--p-text-muted-color);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.group-chip:hover {
  background: var(--p-surface-100);
  color: var(--p-text-color);
}

.sollorm-dark .group-chip:hover {
  background: var(--p-surface-800);
}

.group-chip.active {
  background: rgba(99,102,241,0.1);
  color: var(--p-primary-color);
  border-color: var(--p-primary-color);
}

.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.col-group {
  width: 130px;
  flex-shrink: 0;
}

.group-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.no-group {
  font-size: 0.82rem;
  color: var(--p-text-muted-color);
}

.search-wrap {
  position: relative;
  max-width: 280px;
  width: 100%;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding-left: 2.1rem !important;
  font-size: 0.85rem;
}

/* State boxes */
.state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 4rem;
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
  text-align: center;
}

.state-box.empty i {
  font-size: 2.5rem;
  margin-bottom: 0.25rem;
  opacity: 0.3;
}

/* List */
.list-head {
  display: flex;
  align-items: center;
  padding: 0 1.25rem;
  height: 36px;
  gap: 0;
  background: var(--p-surface-50, rgba(255,255,255,0.02));
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--p-text-muted-color);
}

.agent-row {
  display: flex;
  align-items: center;
  padding: 0 1.25rem;
  height: 52px;
  gap: 0;
  border-bottom: 1px solid var(--p-content-border-color);
  cursor: pointer;
  transition: background 0.15s;
}

.agent-row:last-child { border-bottom: none; }

.agent-row:hover {
  background: var(--p-surface-50, rgba(255,255,255,0.03));
}

.agent-row.offline { opacity: 0.6; }

/* Status dot */
.dot-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-on {
  background: var(--p-green-500);
  box-shadow: 0 0 0 2px rgba(34,197,94,0.25);
}

.dot-off { background: var(--p-surface-400, #64748b); }

.on-label  { font-size: 0.8rem; color: var(--p-green-500); font-weight: 500; }
.off-label { font-size: 0.8rem; color: var(--p-text-muted-color); }

/* Columns */
.col-host {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.hostname {
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-ver {
  font-size: 0.7rem;
  color: var(--p-text-muted-color);
  background: var(--p-content-border-color);
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  flex-shrink: 0;
}

.col-os {
  width: 200px;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.os-icon { color: var(--p-text-muted-color); font-size: 0.9rem; }
.os-label { font-size: 0.82rem; color: var(--p-text-muted-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.col-hw { width: 100px; flex-shrink: 0; }

.hw-val {
  font-size: 0.82rem;
  color: var(--p-text-muted-color);
}

.col-seen { width: 120px; flex-shrink: 0; }

.alert-badge {
  display: inline-flex;
  align-items: center;
  font-size: 0.72rem;
  flex-shrink: 0;
}

.alert-badge.critical { color: var(--p-red-500); }
.alert-badge.warning  { color: var(--p-yellow-500, #f59e0b); }

.update-badge {
  display: inline-flex;
  align-items: center;
  font-size: 0.72rem;
  color: var(--p-blue-400, #60a5fa);
  flex-shrink: 0;
}

.arrow {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  margin-left: auto;
  flex-shrink: 0;
}

/* Responsive */
@media (max-width: 900px) {
  .stats-row { grid-template-columns: repeat(3, 1fr); }
  .col-hw, .col-seen { display: none; }
  .list-head .col-hw, .list-head .col-seen { display: none; }
  .col-os { width: 150px; }
  .group-filters { display: none; }
}

@media (max-width: 600px) {
  .stats-row { grid-template-columns: 1fr 1fr; }
  .col-os, .col-group { display: none; }
}
</style>
