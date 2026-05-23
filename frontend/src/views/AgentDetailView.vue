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

const props = defineProps({
  id: { type: String, required: true }
})

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const deleting = ref(false)

const agent = ref(null)
const heartbeats = ref([])
const loading = ref(true)
const refreshInterval = ref(null)

const lastHeartbeat = computed(() => heartbeats.value[0] || null)

async function loadData() {
  try {
    const [agentRes, hbRes] = await Promise.all([
      agentsApi.get(props.id),
      agentsApi.heartbeats(props.id, 20)
    ])
    agent.value = agentRes.data
    heartbeats.value = hbRes.data
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

@media (max-width: 768px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
