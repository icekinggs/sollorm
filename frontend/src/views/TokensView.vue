<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { agentTokensApi } from '@/api/agentTokens'
import { formatRelativeDate, formatDateTime } from '@/composables/useFormatters'

import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import ConfirmDialog from 'primevue/confirmdialog'
import AddAgentDialog from '@/components/AddAgentDialog.vue'

const toast = useToast()
const confirm = useConfirm()

const tokens = ref([])
const loading = ref(true)
const showDialog = ref(false)

async function loadTokens() {
  loading.value = true
  try {
    const response = await agentTokensApi.list()
    tokens.value = response.data
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Erro',
      detail: 'Falha ao carregar tokens',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

function statusInfo(token) {
  if (token.revoked_at) {
    return { label: 'Revogado', severity: 'danger' }
  }
  if (!token.is_active) {
    return { label: 'Expirado', severity: 'warn' }
  }
  if (token.agent_id) {
    return { label: 'Em uso', severity: 'success' }
  }
  return { label: 'Aguardando', severity: 'info' }
}

function platformIcon(platform) {
  return platform === 'windows' ? 'pi-microsoft' : 'pi-server'
}

function handleRevoke(token) {
  confirm.require({
    message: `Tem certeza que deseja revogar o token "${token.name}"? Esta ação não pode ser desfeita.`,
    header: 'Confirmar revogação',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    acceptLabel: 'Revogar',
    rejectLabel: 'Cancelar',
    accept: async () => {
      try {
        await agentTokensApi.revoke(token.id)
        toast.add({
          severity: 'success',
          summary: 'Token revogado',
          detail: `"${token.name}" não pode mais ser usado`,
          life: 3000
        })
        loadTokens()
      } catch (err) {
        toast.add({
          severity: 'error',
          summary: 'Erro',
          detail: err.response?.data?.detail || 'Falha ao revogar',
          life: 3000
        })
      }
    }
  })
}

function handleDelete(token) {
  confirm.require({
    message: `Apagar o token "${token.name}"? Use só se nunca foi usado.`,
    header: 'Confirmar exclusão',
    icon: 'pi pi-trash',
    acceptClass: 'p-button-danger',
    acceptLabel: 'Apagar',
    rejectLabel: 'Cancelar',
    accept: async () => {
      try {
        await agentTokensApi.delete(token.id)
        toast.add({
          severity: 'success',
          summary: 'Token apagado',
          life: 3000
        })
        loadTokens()
      } catch (err) {
        toast.add({
          severity: 'error',
          summary: 'Erro',
          detail: err.response?.data?.detail || 'Falha ao apagar',
          life: 3000
        })
      }
    }
  })
}

onMounted(loadTokens)
</script>

<template>
  <div class="tokens-page">
    <div class="page-header">
      <div>
        <h2>Tokens de instalação</h2>
        <p class="text-muted">
          Cada token corresponde a uma máquina. Gere um novo para instalar o
          agente em um novo endpoint.
        </p>
      </div>
      <Button
        label="Adicionar agente"
        icon="pi pi-plus"
        @click="showDialog = true"
      />
    </div>

    <div class="card">
      <div v-if="loading && tokens.length === 0" class="loading-state">
        <ProgressSpinner style="width: 32px; height: 32px" stroke-width="4" />
      </div>

      <div v-else-if="tokens.length === 0" class="empty-state">
        <i class="pi pi-key"></i>
        <h3>Nenhum token criado ainda</h3>
        <p>Clique em "Adicionar agente" para gerar o primeiro.</p>
      </div>

      <DataTable
        v-else
        :value="tokens"
        striped-rows
        sort-field="created_at"
        :sort-order="-1"
      >
        <Column header="Status" style="width: 120px">
          <template #body="{ data }">
            <Tag
              :value="statusInfo(data).label"
              :severity="statusInfo(data).severity"
            />
          </template>
        </Column>

        <Column field="name" header="Nome" sortable>
          <template #body="{ data }">
            <div class="name-cell">
              <i :class="['pi', platformIcon(data.platform_hint)]"></i>
              <strong>{{ data.name }}</strong>
            </div>
          </template>
        </Column>

        <Column field="token_prefix" header="Token" style="width: 180px">
          <template #body="{ data }">
            <code class="mono text-muted">{{ data.token_prefix }}...</code>
          </template>
        </Column>

        <Column field="created_at" header="Criado em" sortable style="width: 160px">
          <template #body="{ data }">
            <span class="text-muted">{{ formatRelativeDate(data.created_at) }}</span>
          </template>
        </Column>

        <Column field="last_used_at" header="Último uso" style="width: 160px">
          <template #body="{ data }">
            <span class="text-muted">
              {{ data.last_used_at ? formatRelativeDate(data.last_used_at) : '—' }}
            </span>
          </template>
        </Column>

        <Column field="expires_at" header="Expira" style="width: 140px">
          <template #body="{ data }">
            <span v-if="data.expires_at" class="text-muted">
              {{ formatRelativeDate(data.expires_at) }}
            </span>
            <span v-else class="text-muted">Nunca</span>
          </template>
        </Column>

        <Column header="Ações" style="width: 100px">
          <template #body="{ data }">
            <div class="actions-cell">
              <Button
                v-if="!data.revoked_at"
                icon="pi pi-ban"
                text
                rounded
                severity="danger"
                @click="handleRevoke(data)"
                aria-label="Revogar"
                v-tooltip.top="'Revogar token'"
              />
              <Button
                v-if="!data.agent_id"
                icon="pi pi-trash"
                text
                rounded
                severity="secondary"
                @click="handleDelete(data)"
                aria-label="Apagar"
                v-tooltip.top="'Apagar token'"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <AddAgentDialog
      v-model:visible="showDialog"
      @created="loadTokens"
    />

    <ConfirmDialog />
  </div>
</template>

<style scoped>
.tokens-page {
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 1.5rem;
  gap: 1rem;
}

.page-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.page-header p {
  max-width: 600px;
}

.card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 3rem;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.name-cell i {
  color: var(--p-text-muted-color);
}

.mono {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.85rem;
}

.actions-cell {
  display: flex;
  gap: 0.25rem;
}
</style>
