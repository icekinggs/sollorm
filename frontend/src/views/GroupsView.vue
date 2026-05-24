<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { groupsApi } from '@/api/groups'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import ProgressSpinner from 'primevue/progressspinner'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'

const toast = useToast()
const confirm = useConfirm()

const groups = ref([])
const loading = ref(true)

const showDialog = ref(false)
const editingGroup = ref(null)
const form = ref({ name: '', color: '#6366f1' })
const saving = ref(false)

const PRESET_COLORS = [
  '#6366f1', '#22c55e', '#f59e0b', '#ef4444',
  '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6',
]

async function load() {
  try {
    const res = await groupsApi.list()
    groups.value = res.data
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar grupos', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingGroup.value = null
  form.value = { name: '', color: '#6366f1' }
  showDialog.value = true
}

function openEdit(group) {
  editingGroup.value = group
  form.value = { name: group.name, color: group.color || '#6366f1' }
  showDialog.value = true
}

async function save() {
  if (!form.value.name.trim()) return
  saving.value = true
  try {
    if (editingGroup.value) {
      const res = await groupsApi.update(editingGroup.value.id, form.value)
      const idx = groups.value.findIndex(g => g.id === editingGroup.value.id)
      if (idx !== -1) groups.value[idx] = res.data
      toast.add({ severity: 'success', summary: 'Salvo', detail: 'Grupo atualizado', life: 2000 })
    } else {
      const res = await groupsApi.create(form.value)
      groups.value.push(res.data)
      toast.add({ severity: 'success', summary: 'Criado', detail: `Grupo "${res.data.name}" criado`, life: 2000 })
    }
    showDialog.value = false
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao salvar', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(group) {
  confirm.require({
    message: `Remover o grupo "${group.name}"? Os agentes serão desvinculados.`,
    header: 'Confirmar remoção',
    icon: 'pi pi-trash',
    rejectLabel: 'Cancelar',
    acceptLabel: 'Remover',
    acceptClass: 'p-button-danger',
    accept: () => doDelete(group),
  })
}

async function doDelete(group) {
  try {
    await groupsApi.remove(group.id)
    groups.value = groups.value.filter(g => g.id !== group.id)
    toast.add({ severity: 'success', summary: 'Removido', detail: `Grupo "${group.name}" removido`, life: 2000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: err.response?.data?.detail || 'Falha ao remover', life: 4000 })
  }
}

onMounted(load)
</script>

<template>
  <div class="groups-page">

    <div class="page-header">
      <div>
        <h2>Grupos</h2>
        <span class="sub">Organize agentes em grupos ou clientes</span>
      </div>
      <Button label="Novo grupo" icon="pi pi-plus" @click="openCreate" />
    </div>

    <div v-if="loading" class="state-box">
      <ProgressSpinner style="width:28px;height:28px" stroke-width="3" />
      <span>Carregando...</span>
    </div>

    <div v-else-if="groups.length === 0" class="state-box empty">
      <i class="pi pi-folder" />
      <strong>Nenhum grupo criado</strong>
      <span>Crie um grupo para organizar seus agentes.</span>
      <Button label="Criar primeiro grupo" icon="pi pi-plus" outlined size="small" @click="openCreate" />
    </div>

    <div v-else class="groups-grid">
      <div v-for="group in groups" :key="group.id" class="group-card">
        <div class="group-color-bar" :style="{ background: group.color || '#6366f1' }" />
        <div class="group-body">
          <div class="group-name">{{ group.name }}</div>
          <div class="group-count">
            <i class="pi pi-desktop" />
            {{ group.agent_count }} agente{{ group.agent_count !== 1 ? 's' : '' }}
          </div>
        </div>
        <div class="group-actions">
          <Button icon="pi pi-pencil" text rounded size="small" v-tooltip.top="'Editar'" @click="openEdit(group)" />
          <Button icon="pi pi-trash" text rounded size="small" severity="danger" v-tooltip.top="'Remover'" @click="confirmDelete(group)" />
        </div>
      </div>
    </div>

    <!-- Create / Edit dialog -->
    <Dialog
      v-model:visible="showDialog"
      :header="editingGroup ? 'Editar grupo' : 'Novo grupo'"
      modal
      :style="{ width: '380px' }"
    >
      <div class="dialog-body">
        <label class="field-label">Nome</label>
        <InputText
          v-model="form.name"
          placeholder="Ex: Clientes, Servidores, TI..."
          class="w-full"
          autofocus
          @keyup.enter="save"
        />

        <label class="field-label mt">Cor</label>
        <div class="color-row">
          <button
            v-for="c in PRESET_COLORS"
            :key="c"
            class="color-swatch"
            :style="{ background: c, outline: form.color === c ? `3px solid ${c}` : 'none', outlineOffset: '2px' }"
            @click="form.color = c"
          />
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" text @click="showDialog = false" />
        <Button
          :label="editingGroup ? 'Salvar' : 'Criar'"
          :loading="saving"
          :disabled="!form.name.trim()"
          @click="save"
        />
      </template>
    </Dialog>

    <ConfirmDialog />
  </div>
</template>

<style scoped>
.groups-page {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h2 {
  font-size: 1.35rem;
  font-weight: 700;
  margin: 0 0 0.1rem;
}

.sub {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
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
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
}

.state-box.empty i {
  font-size: 2.5rem;
  margin-bottom: 0.25rem;
  opacity: 0.3;
}

/* Grid */
.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.875rem;
}

.group-card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  align-items: stretch;
  transition: box-shadow 0.15s;
}

.group-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
}

.group-color-bar {
  width: 5px;
  flex-shrink: 0;
}

.group-body {
  flex: 1;
  padding: 0.875rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.group-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.group-count {
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.group-actions {
  display: flex;
  align-items: center;
  padding: 0 0.5rem;
  gap: 0.1rem;
}

/* Dialog */
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding-top: 0.25rem;
}

.field-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-label.mt {
  margin-top: 0.75rem;
}

.color-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.25rem;
}

.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  transition: transform 0.1s;
}

.color-swatch:hover {
  transform: scale(1.15);
}
</style>
