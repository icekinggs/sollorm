<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { agentsApi } from '@/api/agents'
import {
  formatBytes,
  formatRelativeDate,
  usageColorClass
} from '@/composables/useFormatters'

import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'

const router = useRouter()
const toast = useToast()

const agents = ref([])
const loading = ref(true)
const lastRefresh = ref(null)
const refreshInterval = ref(null)

const metrics = computed(() => {
  const total = agents.value.length
  const online = agents.value.filter((a) => a.is_online).length
  return {
    total,
    online,
    offline: total - online
  }
})

async function loadAgents(showToast = false) {
  try {
    const response = await agentsApi.list()
    agents.value = response.data
    lastRefresh.value = new Date()

    if (showToast) {
      toast.add({
        severity: 'success',
        summary: 'Atualizado',
        detail: `${response.data.length} agentes carregados`,
        life: 2000
      })
    }
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Erro',
      detail: err.response?.data?.detail || 'Falha ao carregar agentes',
      life: 4000
    })
  } finally {
    loading.value = false
  }
}

function openAgent(event) {
  router.push({ name: 'agent-detail', params: { id: event.data.id } })
}

onMounted(() => {
  loadAgents()
  refreshInterval.value = setInterval(() => loadAgents(false), 30000)
})

onUnmounted(() => {
  if (refreshInterval.value) clearInterval(refreshInterval.value)
})
</script>

<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <div>
        <h2>Dashboard</h2>
        <p class="text-muted" v-if="lastRefresh">
          Atualizado {{ formatRelativeDate(lastRefresh.toISOString()) }}
        </p>
      </div>
      <Button
        icon="pi pi-refresh"
        label="Atualizar"
        outlined
        :loading="loading"
        @click="loadAgents(true)"
      />
    </div>

    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-label">Total de agentes</div>
        <div class="metric-value">{{ metrics.total }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Online</div>
        <div class="metric-value text-success">{{ metrics.online }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Offline</div>
        <div class="metric-value text-danger">{{ metrics.offline }}</div>
      </div>
    </div>

    <div class="card">
      <div v-if="loading && agents.length === 0" class="loading-state">
        <ProgressSpinner style="width: 32px; height: 32px" stroke-width="4" />
        <span class="text-muted">Carregando agentes...</span>
      </div>

      <div v-else-if="agents.length === 0" class="empty-state">
        <i class="pi pi-desktop"></i>
        <h3>Nenhum agente registrado</h3>
        <p>Compile e rode um agente para vê-lo aparecer aqui.</p>
      </div>

      <DataTable
        v-else
        :value="agents"
        striped-rows
        :row-hover="true"
        @row-click="openAgent"
        class="agent-table"
        sort-field="hostname"
        :sort-order="1"
      >
        <Column field="is_online" header="Status" style="width: 90px">
          <template #body="{ data }">
            <Tag
              :value="data.is_online ? 'Online' : 'Offline'"
              :severity="data.is_online ? 'success' : 'secondary'"
            />
          </template>
        </Column>

        <Column field="hostname" header="Hostname" sortable>
          <template #body="{ data }">
            <strong>{{ data.hostname }}</strong>
          </template>
        </Column>

        <Column field="platform" header="Sistema" sortable>
          <template #body="{ data }">
            <div class="os-cell">
              <i :class="['pi', data.os === 'windows' ? 'pi-microsoft' : 'pi-server']"></i>
              <span class="text-muted">{{ data.platform || '—' }}</span>
            </div>
          </template>
        </Column>

        <Column field="cpu_cores" header="CPU" style="width: 120px">
          <template #body="{ data }">
            <span v-if="data.cpu_cores" class="text-muted">
              {{ data.cpu_cores }} cores
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </Column>

        <Column field="ram_total_bytes" header="RAM" style="width: 120px">
          <template #body="{ data }">
            <span class="text-muted">{{ formatBytes(data.ram_total_bytes) }}</span>
          </template>
        </Column>

        <Column field="disk_total_bytes" header="Disco" style="width: 120px">
          <template #body="{ data }">
            <span class="text-muted">{{ formatBytes(data.disk_total_bytes) }}</span>
          </template>
        </Column>

        <Column field="last_seen" header="Last seen" sortable style="width: 160px">
          <template #body="{ data }">
            <span class="text-muted">{{ formatRelativeDate(data.last_seen) }}</span>
          </template>
        </Column>

        <Column header="" style="width: 50px">
          <template #body>
            <i class="pi pi-chevron-right text-muted"></i>
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 1.5rem;
}

.dashboard-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
}

.metric-card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 1rem 1.25rem;
}

.metric-label {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  margin-bottom: 0.4rem;
}

.metric-value {
  font-size: 1.75rem;
  font-weight: 600;
}

.text-success {
  color: var(--p-green-500);
}

.text-danger {
  color: var(--p-text-muted-color);
}

.card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  gap: 1rem;
}

.os-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.os-cell i {
  color: var(--p-text-muted-color);
}

.agent-table :deep(.p-datatable-tbody > tr) {
  cursor: pointer;
}
</style>
