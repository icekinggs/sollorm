<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { agentsApi } from '@/api/agents'
import { formatDateTime, formatRelativeDate } from '@/composables/useFormatters'

import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import Checkbox from 'primevue/checkbox'

const props = defineProps({
  agentId: { type: String, required: true }
})

const toast = useToast()

const scan = ref(null)
const items = ref([])
const loading = ref(false)
const scanning = ref(false)
const installing = ref(false)
const selected = ref([])

const pendingItems = computed(() => items.value.filter(i => !i.installed))
const installedItems = computed(() => items.value.filter(i => i.installed))
const hasPending = computed(() => pendingItems.value.length > 0)

function severityTag(s) {
  if (s === 'security') return 'danger'
  if (s === 'unknown') return 'secondary'
  return 'secondary'
}

function scanStatusSeverity(s) {
  if (s === 'done') return 'success'
  if (s === 'scanning') return 'info'
  if (s === 'error') return 'danger'
  return 'secondary'
}

async function loadPatches() {
  loading.value = true
  try {
    const res = await agentsApi.patchGet(props.agentId)
    if (res.data) {
      scan.value = res.data.scan
      items.value = res.data.items
    } else {
      scan.value = null
      items.value = []
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar patches', life: 3000 })
  } finally {
    loading.value = false
  }
}

async function triggerScan() {
  scanning.value = true
  selected.value = []
  try {
    const res = await agentsApi.patchScan(props.agentId)
    scan.value = res.data
    items.value = []
    toast.add({ severity: 'info', summary: 'Scan iniciado', detail: 'Aguardando resultado do agente...', life: 4000 })
    // poll until done or error
    let attempts = 0
    const poll = setInterval(async () => {
      attempts++
      await loadPatches()
      if (scan.value?.status !== 'scanning' || attempts >= 30) {
        clearInterval(poll)
        scanning.value = false
      }
    }, 3000)
  } catch (err) {
    scanning.value = false
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao iniciar scan', life: 4000 })
  }
}

async function installSelected() {
  if (!selected.value.length) return
  installing.value = true
  try {
    const names = selected.value.map(i => i.name)
    await agentsApi.patchInstall(props.agentId, names)
    toast.add({ severity: 'success', summary: 'Instalação enviada', detail: `${names.length} pacote(s) enviados`, life: 3000 })
    selected.value = []
    setTimeout(loadPatches, 5000)
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao instalar', life: 4000 })
  } finally {
    installing.value = false
  }
}

async function installAll() {
  installing.value = true
  try {
    const res = await agentsApi.patchInstallAll(props.agentId)
    toast.add({ severity: 'success', summary: 'Instalação enviada', detail: res.data.message, life: 3000 })
    selected.value = []
    setTimeout(loadPatches, 5000)
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao instalar tudo', life: 4000 })
  } finally {
    installing.value = false
  }
}

onMounted(loadPatches)
</script>

<template>
  <div class="patch-manager">

    <!-- Toolbar -->
    <div class="patch-toolbar">
      <div class="scan-info" v-if="scan">
        <Tag :value="scan.status" :severity="scanStatusSeverity(scan.status)" />
        <span class="text-muted scan-meta">
          Scan {{ formatRelativeDate(scan.requested_at) }}
          <template v-if="scan.patch_count != null"> · {{ scan.patch_count }} pacote(s)</template>
        </span>
        <span v-if="scan.error_message" class="scan-error text-muted">· {{ scan.error_message }}</span>
      </div>
      <div class="scan-info text-muted" v-else-if="!loading">
        Nenhum scan realizado ainda
      </div>
      <div class="toolbar-spacer" />
      <Button
        v-if="selected.length > 0"
        :label="`Instalar selecionados (${selected.length})`"
        icon="pi pi-download"
        severity="warning"
        :loading="installing"
        @click="installSelected"
      />
      <Button
        v-if="hasPending && scan?.status === 'done'"
        label="Instalar tudo"
        icon="pi pi-cloud-download"
        :loading="installing"
        @click="installAll"
      />
      <Button
        label="Escanear"
        icon="pi pi-refresh"
        severity="secondary"
        :loading="scanning || loading"
        @click="triggerScan"
      />
    </div>

    <!-- Loading spinner -->
    <div v-if="loading" class="patch-loading">
      <ProgressSpinner style="width:28px;height:28px" stroke-width="3" />
      <span class="text-muted">Carregando...</span>
    </div>

    <!-- No scan yet -->
    <div v-else-if="!scan" class="patch-empty">
      <i class="pi pi-shield" />
      <p>Clique em <strong>Escanear</strong> para verificar atualizações disponíveis neste host.</p>
    </div>

    <!-- Scanning in progress -->
    <div v-else-if="scan.status === 'scanning'" class="patch-scanning">
      <ProgressSpinner style="width:28px;height:28px" stroke-width="3" />
      <span class="text-muted">Aguardando resultado do agente...</span>
    </div>

    <!-- Results -->
    <template v-else-if="scan.status === 'done'">

      <!-- Pending -->
      <div class="section-label">
        <i class="pi pi-exclamation-circle text-muted" />
        <span>Pendentes ({{ pendingItems.length }})</span>
      </div>

      <DataTable
        v-model:selection="selected"
        :value="pendingItems"
        striped-rows
        data-key="id"
        class="patch-table"
      >
        <template #empty>
          <div class="table-empty">Nenhuma atualização pendente.</div>
        </template>
        <Column selection-mode="multiple" style="width: 3rem" />
        <Column field="name" header="Pacote" />
        <Column field="current_version" header="Atual" style="width: 160px">
          <template #body="{ data }">{{ data.current_version || '—' }}</template>
        </Column>
        <Column field="available_version" header="Disponível" style="width: 160px">
          <template #body="{ data }">{{ data.available_version || '—' }}</template>
        </Column>
        <Column field="severity" header="Severidade" style="width: 130px">
          <template #body="{ data }">
            <Tag :value="data.severity || 'unknown'" :severity="severityTag(data.severity)" />
          </template>
        </Column>
        <Column field="source" header="Fonte" style="width: 100px">
          <template #body="{ data }"><code class="mono">{{ data.source || '—' }}</code></template>
        </Column>
      </DataTable>

      <!-- Installed -->
      <div class="section-label mt" v-if="installedItems.length">
        <i class="pi pi-check-circle text-muted" />
        <span>Instalados ({{ installedItems.length }})</span>
      </div>

      <DataTable
        v-if="installedItems.length"
        :value="installedItems"
        striped-rows
        data-key="id"
        class="patch-table installed-table"
      >
        <Column field="name" header="Pacote" />
        <Column field="available_version" header="Versão" style="width: 160px">
          <template #body="{ data }">{{ data.available_version || '—' }}</template>
        </Column>
        <Column field="source" header="Fonte" style="width: 100px">
          <template #body="{ data }"><code class="mono">{{ data.source || '—' }}</code></template>
        </Column>
        <Column field="installed_at" header="Instalado em" style="width: 200px">
          <template #body="{ data }">{{ formatDateTime(data.installed_at) }}</template>
        </Column>
      </DataTable>

    </template>

    <!-- Error -->
    <div v-else-if="scan.status === 'error'" class="patch-error">
      <i class="pi pi-times-circle" />
      <span>Erro no scan: {{ scan.error_message || 'desconhecido' }}</span>
    </div>

  </div>
</template>

<style scoped>
.patch-manager {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 0.5rem 0;
}

.patch-toolbar {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex-wrap: wrap;
}

.toolbar-spacer { flex: 1; }

.scan-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.scan-meta { font-size: 0.8rem; }

.scan-error {
  font-size: 0.8rem;
  color: var(--p-red-500) !important;
}

.patch-loading,
.patch-scanning {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
  font-size: 0.875rem;
}

.patch-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  gap: 0.75rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.patch-empty i {
  font-size: 2rem;
}

.patch-empty p {
  font-size: 0.875rem;
  max-width: 420px;
  margin: 0;
}

.patch-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  color: var(--p-red-500);
  font-size: 0.875rem;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--p-text-muted-color);
}

.section-label.mt { margin-top: 0.5rem; }

.installed-table :deep(tr) {
  opacity: 0.6;
}

.table-empty {
  padding: 1.5rem;
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

.mono {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.8rem;
}
</style>
