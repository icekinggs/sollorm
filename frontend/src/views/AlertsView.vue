<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { alertsApi } from '@/api/alerts'
import { agentsApi } from '@/api/agents'
import { formatRelativeDate } from '@/composables/useFormatters'
import { useNotifications } from '@/composables/useNotifications'

import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import ToggleSwitch from 'primevue/toggleswitch'
import ConfirmDialog from 'primevue/confirmdialog'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()

const rules = ref([])
const events = ref([])
const agents = ref([])
const loading = ref(true)

const showRuleDialog = ref(false)
const editingRule = ref(null)
const saving = ref(false)
const form = ref({ name: '', agent_id: null, metric: 'cpu_usage_percent', operator: '>', threshold: 90, severity: 'warning' })

const METRIC_OPTIONS = [
  { label: 'CPU', value: 'cpu_usage_percent' },
  { label: 'RAM', value: 'ram_usage_percent' },
  { label: 'Disco', value: 'disk_usage_percent' },
]

const OPERATOR_OPTIONS = [
  { label: '> maior que', value: '>' },
  { label: '>= maior ou igual', value: '>=' },
  { label: '< menor que', value: '<' },
  { label: '<= menor ou igual', value: '<=' },
]

const SEVERITY_OPTIONS = [
  { label: 'Aviso', value: 'warning' },
  { label: 'Crítico', value: 'critical' },
]

const agentOptions = computed(() => [
  { label: 'Todos os agentes', value: null },
  ...agents.value.map(a => ({ label: a.hostname, value: a.id }))
])

const firingEvents = computed(() => events.value.filter(e => e.state === 'firing'))
const recentResolved = computed(() => events.value.filter(e => e.state === 'resolved').slice(0, 20))

function metricLabel(m) {
  return { cpu_usage_percent: 'CPU', ram_usage_percent: 'RAM', disk_usage_percent: 'Disco' }[m] || m
}

function severityTag(s) {
  return s === 'critical' ? 'danger' : 'warn'
}

async function load() {
  try {
    const [rulesRes, eventsRes, agentsRes] = await Promise.all([
      alertsApi.listRules(),
      alertsApi.listEvents({ limit: 100 }),
      agentsApi.list(),
    ])
    rules.value = rulesRes.data
    events.value = eventsRes.data
    agents.value = agentsRes.data
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingRule.value = null
  form.value = { name: '', agent_id: null, metric: 'cpu_usage_percent', operator: '>', threshold: 90, severity: 'warning' }
  showRuleDialog.value = true
}

function openEdit(rule) {
  editingRule.value = rule
  form.value = { name: rule.name, agent_id: rule.agent_id, metric: rule.metric, operator: rule.operator, threshold: rule.threshold, severity: rule.severity }
  showRuleDialog.value = true
}

async function save() {
  if (!form.value.name.trim()) return
  saving.value = true
  try {
    if (editingRule.value) {
      const res = await alertsApi.updateRule(editingRule.value.id, form.value)
      const idx = rules.value.findIndex(r => r.id === editingRule.value.id)
      if (idx !== -1) rules.value[idx] = res.data
      toast.add({ severity: 'success', summary: 'Salvo', detail: 'Regra atualizada', life: 2000 })
    } else {
      const res = await alertsApi.createRule(form.value)
      rules.value.unshift(res.data)
      toast.add({ severity: 'success', summary: 'Criado', detail: `Regra "${res.data.name}" criada`, life: 2000 })
    }
    showRuleDialog.value = false
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao salvar', life: 4000 })
  } finally {
    saving.value = false
  }
}

async function toggleRule(rule) {
  try {
    const res = await alertsApi.updateRule(rule.id, { enabled: !rule.enabled })
    const idx = rules.value.findIndex(r => r.id === rule.id)
    if (idx !== -1) rules.value[idx] = res.data
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao atualizar', life: 3000 })
  }
}

function confirmDeleteRule(rule) {
  confirm.require({
    message: `Remover a regra "${rule.name}"?`,
    header: 'Confirmar remoção',
    icon: 'pi pi-trash',
    acceptLabel: 'Remover',
    rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await alertsApi.removeRule(rule.id)
        rules.value = rules.value.filter(r => r.id !== rule.id)
        toast.add({ severity: 'success', summary: 'Removido', life: 2000 })
      } catch {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao remover', life: 3000 })
      }
    }
  })
}

// Real-time updates
useNotifications((msg) => {
  if (msg.type === 'alert_fired') {
    events.value.unshift({
      id: msg.event_id,
      rule_id: msg.rule_id,
      rule_name: msg.rule_name,
      agent_id: msg.agent_id,
      agent_hostname: agents.value.find(a => a.id === msg.agent_id)?.hostname,
      metric: msg.metric,
      value: msg.value,
      threshold: msg.threshold,
      operator: msg.operator,
      severity: msg.severity,
      state: 'firing',
      fired_at: msg.fired_at,
      resolved_at: null,
    })
  } else if (msg.type === 'alert_resolved') {
    const ev = events.value.find(e => e.id === msg.event_id)
    if (ev) { ev.state = 'resolved'; ev.resolved_at = msg.resolved_at }
  }
})

onMounted(load)
</script>

<template>
  <div class="alerts-page">

    <div class="page-header">
      <div>
        <h2>Alertas</h2>
        <span class="sub">Regras de threshold e eventos ativos</span>
      </div>
      <Button label="Nova regra" icon="pi pi-plus" @click="openCreate" />
    </div>

    <div v-if="loading" class="state-box">
      <ProgressSpinner style="width:28px;height:28px" stroke-width="3" />
    </div>

    <template v-else>

      <!-- Active alerts -->
      <div class="section">
        <div class="section-head">
          <span class="section-title">Ativos</span>
          <span v-if="firingEvents.length" class="count-badge firing">{{ firingEvents.length }}</span>
        </div>

        <div v-if="firingEvents.length === 0" class="empty-section">
          <i class="pi pi-check-circle" />
          <span>Nenhum alerta ativo</span>
        </div>

        <div v-else class="event-list">
          <div
            v-for="ev in firingEvents"
            :key="ev.id"
            class="event-row firing"
            :class="ev.severity"
            @click="router.push({ name: 'agent-detail', params: { id: ev.agent_id } })"
          >
            <i :class="['pi', ev.severity === 'critical' ? 'pi-times-circle' : 'pi-exclamation-triangle', 'ev-icon']" />
            <div class="ev-body">
              <span class="ev-agent">{{ ev.agent_hostname || ev.agent_id }}</span>
              <span class="ev-desc">
                {{ metricLabel(ev.metric) }} {{ ev.operator }} {{ ev.threshold }}% — valor atual: <strong>{{ ev.value?.toFixed(1) }}%</strong>
              </span>
            </div>
            <Tag :value="ev.severity === 'critical' ? 'Crítico' : 'Aviso'" :severity="severityTag(ev.severity)" />
            <span class="ev-time">{{ formatRelativeDate(ev.fired_at) }}</span>
            <i class="pi pi-chevron-right ev-arrow" />
          </div>
        </div>
      </div>

      <!-- Rules -->
      <div class="section">
        <div class="section-head">
          <span class="section-title">Regras</span>
          <span class="count-badge">{{ rules.length }}</span>
        </div>

        <div v-if="rules.length === 0" class="empty-section">
          <i class="pi pi-sliders-h" />
          <span>Nenhuma regra criada</span>
          <Button label="Criar primeira regra" icon="pi pi-plus" outlined size="small" @click="openCreate" />
        </div>

        <div v-else class="rules-list">
          <div v-for="rule in rules" :key="rule.id" class="rule-row">
            <ToggleSwitch :model-value="rule.enabled" @change="toggleRule(rule)" />
            <div class="rule-body">
              <span class="rule-name">{{ rule.name }}</span>
              <span class="rule-desc">
                {{ metricLabel(rule.metric) }} {{ rule.operator }} {{ rule.threshold }}%
                <span v-if="rule.agent_id"> · {{ agents.find(a=>a.id===rule.agent_id)?.hostname || rule.agent_id }}</span>
                <span v-else> · Todos os agentes</span>
              </span>
            </div>
            <Tag :value="rule.severity === 'critical' ? 'Crítico' : 'Aviso'" :severity="severityTag(rule.severity)" />
            <Button icon="pi pi-pencil" text rounded size="small" @click="openEdit(rule)" />
            <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="confirmDeleteRule(rule)" />
          </div>
        </div>
      </div>

      <!-- Recent resolved -->
      <div class="section" v-if="recentResolved.length">
        <div class="section-head">
          <span class="section-title">Resolvidos recentes</span>
        </div>
        <div class="event-list">
          <div
            v-for="ev in recentResolved"
            :key="ev.id"
            class="event-row resolved"
            @click="router.push({ name: 'agent-detail', params: { id: ev.agent_id } })"
          >
            <i class="pi pi-check-circle ev-icon resolved" />
            <div class="ev-body">
              <span class="ev-agent">{{ ev.agent_hostname || ev.agent_id }}</span>
              <span class="ev-desc">{{ metricLabel(ev.metric) }} {{ ev.operator }} {{ ev.threshold }}%</span>
            </div>
            <span class="ev-time">{{ formatRelativeDate(ev.resolved_at) }}</span>
            <i class="pi pi-chevron-right ev-arrow" />
          </div>
        </div>
      </div>

    </template>

    <!-- Rule dialog -->
    <Dialog
      v-model:visible="showRuleDialog"
      :header="editingRule ? 'Editar regra' : 'Nova regra de alerta'"
      modal
      :style="{ width: '420px' }"
    >
      <div class="dialog-form">
        <div class="field">
          <label>Nome</label>
          <InputText v-model="form.name" placeholder="Ex: CPU alta, Disco cheio..." class="w-full" autofocus />
        </div>
        <div class="field">
          <label>Agente</label>
          <Select v-model="form.agent_id" :options="agentOptions" option-label="label" option-value="value" class="w-full" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>Métrica</label>
            <Select v-model="form.metric" :options="METRIC_OPTIONS" option-label="label" option-value="value" class="w-full" />
          </div>
          <div class="field">
            <label>Operador</label>
            <Select v-model="form.operator" :options="OPERATOR_OPTIONS" option-label="label" option-value="value" class="w-full" />
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label>Threshold (%)</label>
            <InputNumber v-model="form.threshold" :min="0" :max="100" suffix="%" class="w-full" />
          </div>
          <div class="field">
            <label>Severidade</label>
            <Select v-model="form.severity" :options="SEVERITY_OPTIONS" option-label="label" option-value="value" class="w-full" />
          </div>
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" text @click="showRuleDialog = false" />
        <Button :label="editingRule ? 'Salvar' : 'Criar'" :loading="saving" :disabled="!form.name.trim()" @click="save" />
      </template>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<style scoped>
.alerts-page {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h2 { font-size: 1.35rem; font-weight: 700; margin: 0 0 0.1rem; }
.sub { font-size: 0.8rem; color: var(--p-text-muted-color); }

/* Sections */
.section {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  overflow: hidden;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.section-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--p-text-muted-color);
}

.count-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: var(--p-content-border-color);
  color: var(--p-text-muted-color);
}

.count-badge.firing {
  background: rgba(239, 68, 68, 0.15);
  color: var(--p-red-500);
}

.empty-section {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0.4rem;
  padding: 2.5rem;
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

.empty-section .pi { font-size: 1.8rem; opacity: 0.25; }

/* State box */
.state-box {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4rem;
}

/* Event rows */
.event-list { display: flex; flex-direction: column; }

.event-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--p-content-border-color);
  cursor: pointer;
  transition: background 0.15s;
}

.event-row:last-child { border-bottom: none; }
.event-row:hover { background: var(--p-surface-50, rgba(255,255,255,0.03)); }

.event-row.resolved { opacity: 0.55; }

.ev-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
}

.event-row.firing.warning .ev-icon { color: var(--p-yellow-500, #f59e0b); }
.event-row.firing.critical .ev-icon { color: var(--p-red-500); }
.ev-icon.resolved { color: var(--p-green-500); }

.ev-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.ev-agent { font-weight: 600; font-size: 0.875rem; }
.ev-desc  { font-size: 0.8rem; color: var(--p-text-muted-color); }

.ev-time {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.ev-arrow { font-size: 0.75rem; color: var(--p-text-muted-color); flex-shrink: 0; }

/* Rules */
.rules-list { display: flex; flex-direction: column; }

.rule-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.rule-row:last-child { border-bottom: none; }

.rule-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.rule-name { font-weight: 600; font-size: 0.875rem; }
.rule-desc { font-size: 0.78rem; color: var(--p-text-muted-color); }

/* Dialog */
.dialog-form { display: flex; flex-direction: column; gap: 0.875rem; padding-top: 0.25rem; }

.field { display: flex; flex-direction: column; gap: 0.3rem; flex: 1; }
.field label { font-size: 0.78rem; font-weight: 600; color: var(--p-text-muted-color); text-transform: uppercase; letter-spacing: 0.05em; }

.field-row { display: flex; gap: 0.75rem; }
</style>
