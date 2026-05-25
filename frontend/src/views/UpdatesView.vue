<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import updatesApi from '@/api/updates'
import { formatRelativeDate } from '@/composables/useFormatters'

import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import ConfirmDialog from 'primevue/confirmdialog'
import Textarea from 'primevue/textarea'

const toast = useToast()
const confirm = useConfirm()

const statusData = ref(null)
const approvals = ref([])
const loading = ref(true)

const showApproveDialog = ref(false)
const saving = ref(false)
const form = ref({ version: '', scope: 'global', group_id: null, notes: '' })

const SCOPE_OPTIONS = [
  { label: 'Todos os grupos (global)', value: 'global' },
  { label: 'Grupo específico', value: 'group' },
  { label: 'Sem grupo', value: 'ungrouped' },
]

const groupOptions = computed(() => {
  if (!statusData.value) return []
  return statusData.value.groups
    .filter(g => g.group_id !== null)
    .map(g => ({ label: g.group_name, value: g.group_id }))
})

async function load() {
  loading.value = true
  try {
    const [statusRes, approvalsRes] = await Promise.all([
      updatesApi.status(),
      updatesApi.list(),
    ])
    statusData.value = statusRes.data
    approvals.value = approvalsRes.data
    form.value.version = statusRes.data.latest_version
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openApprove(group = null) {
  if (group) {
    if (group.group_id === null) {
      form.value.scope = 'ungrouped'
      form.value.group_id = null
    } else {
      form.value.scope = 'group'
      form.value.group_id = group.group_id
    }
  } else {
    form.value.scope = 'global'
    form.value.group_id = null
  }
  form.value.version = statusData.value?.latest_version || ''
  form.value.notes = ''
  showApproveDialog.value = true
}

async function submitApproval() {
  if (!form.value.version.trim()) return
  saving.value = true
  try {
    const payload = {
      version: form.value.version.trim(),
      is_global: form.value.scope === 'global',
      group_id: form.value.scope === 'group' ? form.value.group_id : null,
      notes: form.value.notes || null,
    }
    await updatesApi.create(payload)
    toast.add({ severity: 'success', summary: 'Aprovado', detail: `Versão ${payload.version} aprovada`, life: 3000 })
    showApproveDialog.value = false
    await load()
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao aprovar', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmRevoke(approval) {
  confirm.require({
    message: `Revogar aprovação da versão ${approval.version} para "${approval.group_name}"?`,
    header: 'Confirmar revogação',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: 'Revogar',
    rejectLabel: 'Cancelar',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await updatesApi.revoke(approval.id)
        approvals.value = approvals.value.filter(a => a.id !== approval.id)
        toast.add({ severity: 'success', summary: 'Revogado', life: 2000 })
        await load()
      } catch {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao revogar', life: 3000 })
      }
    }
  })
}

function versionStatusColor(group) {
  if (!group.approved_version) return 'secondary'
  const pending = Object.entries(group.versions).some(
    ([v]) => v !== group.approved_version
  )
  const allUpdated = group.agent_count > 0 && Object.entries(group.versions).every(
    ([v]) => v === group.approved_version
  )
  if (allUpdated) return 'success'
  if (pending) return 'warn'
  return 'info'
}

function pendingCount(group) {
  if (!group.approved_version) return 0
  return Object.entries(group.versions)
    .filter(([v]) => v !== group.approved_version)
    .reduce((sum, [, n]) => sum + n, 0)
}

onMounted(load)
</script>

<template>
  <div class="updates-page">

    <div class="page-header">
      <div>
        <h2>Atualizações de Agente</h2>
        <span class="sub">Controle de versão por grupo — estilo WSUS</span>
      </div>
      <Button label="Aprovar versão global" icon="pi pi-check-circle" @click="openApprove()" />
    </div>

    <div v-if="loading" class="state-box">
      <ProgressSpinner style="width:28px;height:28px" stroke-width="3" />
    </div>

    <template v-else-if="statusData">

      <!-- Latest version banner -->
      <div class="version-banner">
        <i class="pi pi-info-circle" />
        <span>Versão mais recente detectada no GitHub: <strong>{{ statusData.latest_version }}</strong></span>
      </div>

      <!-- Group status grid -->
      <div class="section">
        <div class="section-head">
          <span class="section-title">Status por grupo</span>
          <span class="count-badge">{{ statusData.groups.length }}</span>
        </div>

        <div class="groups-grid">
          <div
            v-for="group in statusData.groups"
            :key="group.group_id ?? '__ungrouped__'"
            class="group-card"
          >
            <div class="group-card-header">
              <span
                class="group-dot"
                :style="group.group_color ? { background: group.group_color } : {}"
              />
              <span class="group-name">{{ group.group_name }}</span>
              <span class="agent-count">{{ group.agent_count }} agente{{ group.agent_count !== 1 ? 's' : '' }}</span>
            </div>

            <div class="approved-row">
              <span class="label">Versão aprovada</span>
              <Tag
                v-if="group.approved_version"
                :value="group.approved_version"
                :severity="versionStatusColor(group)"
              />
              <span v-else class="none-tag">Nenhuma</span>
            </div>

            <div v-if="Object.keys(group.versions).length" class="versions-breakdown">
              <div
                v-for="(count, ver) in group.versions"
                :key="ver"
                class="ver-row"
              >
                <span class="ver-name">{{ ver }}</span>
                <span class="ver-count">{{ count }}</span>
                <i
                  v-if="group.approved_version && ver === group.approved_version"
                  class="pi pi-check ver-ok"
                />
                <i
                  v-else-if="group.approved_version"
                  class="pi pi-arrow-up ver-pending"
                />
              </div>
            </div>

            <div v-if="pendingCount(group) > 0" class="pending-note">
              <i class="pi pi-clock" />
              {{ pendingCount(group) }} aguardando atualização
            </div>

            <Button
              :label="group.approved_version ? 'Alterar aprovação' : 'Aprovar versão'"
              :icon="group.approved_version ? 'pi pi-sync' : 'pi pi-check'"
              size="small"
              :outlined="!!group.approved_version"
              class="approve-btn"
              @click="openApprove(group)"
            />
          </div>
        </div>
      </div>

      <!-- Approval history -->
      <div class="section">
        <div class="section-head">
          <span class="section-title">Histórico de aprovações</span>
          <span class="count-badge">{{ approvals.length }}</span>
        </div>

        <div v-if="approvals.length === 0" class="empty-section">
          <i class="pi pi-history" />
          <span>Nenhuma aprovação registrada</span>
        </div>

        <div v-else class="approval-list">
          <div v-for="ap in approvals" :key="ap.id" class="approval-row">
            <div class="ap-scope">
              <i :class="['pi', ap.is_global ? 'pi-globe' : 'pi-folder']" />
              <span>{{ ap.group_name }}</span>
            </div>
            <Tag :value="ap.version" severity="info" />
            <div class="ap-meta">
              <span>por <strong>{{ ap.approved_by }}</strong></span>
              <span class="ap-date">{{ formatRelativeDate(ap.approved_at) }}</span>
            </div>
            <Tag v-if="ap.active" value="Ativo" severity="success" />
            <Tag v-else value="Revogado" severity="secondary" />
            <span v-if="ap.notes" class="ap-notes" :title="ap.notes">
              <i class="pi pi-comment" /> {{ ap.notes }}
            </span>
            <Button
              v-if="ap.active"
              icon="pi pi-times"
              text
              rounded
              size="small"
              severity="danger"
              v-tooltip.top="'Revogar'"
              @click="confirmRevoke(ap)"
            />
          </div>
        </div>
      </div>

    </template>

    <!-- Approve dialog -->
    <Dialog
      v-model:visible="showApproveDialog"
      header="Aprovar versão"
      modal
      :style="{ width: '420px' }"
    >
      <div class="dialog-form">
        <div class="field">
          <label>Escopo</label>
          <Select
            v-model="form.scope"
            :options="SCOPE_OPTIONS"
            option-label="label"
            option-value="value"
            class="w-full"
          />
        </div>

        <div v-if="form.scope === 'group'" class="field">
          <label>Grupo</label>
          <Select
            v-model="form.group_id"
            :options="groupOptions"
            option-label="label"
            option-value="value"
            placeholder="Selecione o grupo"
            class="w-full"
          />
        </div>

        <div class="field">
          <label>Versão</label>
          <InputText v-model="form.version" placeholder="Ex: v0.6.0" class="w-full" />
          <span class="field-hint">Última versão detectada: {{ statusData?.latest_version }}</span>
        </div>

        <div class="field">
          <label>Notas (opcional)</label>
          <Textarea v-model="form.notes" rows="2" placeholder="Motivo da aprovação..." class="w-full" />
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" text @click="showApproveDialog = false" />
        <Button
          label="Aprovar e enviar"
          icon="pi pi-check"
          :loading="saving"
          :disabled="!form.version.trim() || (form.scope === 'group' && !form.group_id)"
          @click="submitApproval"
        />
      </template>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<style scoped>
.updates-page {
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

.version-banner {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.75rem 1rem;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 8px;
  font-size: 0.875rem;
  color: var(--p-text-color);
}

.version-banner .pi { color: var(--p-blue-400); }

.state-box {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4rem;
}

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

/* Group grid */
.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.group-card {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.group-card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.group-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--p-text-muted-color);
  flex-shrink: 0;
}

.group-name {
  font-weight: 600;
  font-size: 0.9rem;
  flex: 1;
}

.agent-count {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

.approved-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.approved-row .label {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

.none-tag {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  font-style: italic;
}

.versions-breakdown {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  background: var(--p-surface-100, rgba(0,0,0,0.04));
  border-radius: 6px;
  padding: 0.5rem 0.6rem;
}

.ver-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
}

.ver-name { flex: 1; font-family: monospace; }
.ver-count { font-weight: 600; color: var(--p-text-muted-color); }
.ver-ok { color: var(--p-green-500); font-size: 0.7rem; }
.ver-pending { color: var(--p-yellow-500, #f59e0b); font-size: 0.7rem; }

.pending-note {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--p-yellow-500, #f59e0b);
}

.approve-btn { width: 100%; justify-content: center; }

/* Approval list */
.approval-list { display: flex; flex-direction: column; }

.approval-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--p-content-border-color);
  flex-wrap: wrap;
}

.approval-row:last-child { border-bottom: none; }

.ap-scope {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 600;
  min-width: 160px;
}

.ap-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
}

.ap-date { font-size: 0.72rem; }

.ap-notes {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  font-style: italic;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Dialog */
.dialog-form { display: flex; flex-direction: column; gap: 0.875rem; padding-top: 0.25rem; }
.field { display: flex; flex-direction: column; gap: 0.3rem; }
.field label { font-size: 0.78rem; font-weight: 600; color: var(--p-text-muted-color); text-transform: uppercase; letter-spacing: 0.05em; }
.field-hint { font-size: 0.75rem; color: var(--p-text-muted-color); }
</style>
