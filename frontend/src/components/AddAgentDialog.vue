<script setup>
import { ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import { agentTokensApi } from '@/api/agentTokens'

import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Textarea from 'primevue/textarea'
import Tag from 'primevue/tag'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'created'])

const toast = useToast()

const step = ref(1) // 1 = form, 2 = token gerado
const loading = ref(false)
const errorMessage = ref('')

const form = ref({
  name: '',
  platform_hint: 'windows',
  expires_in_days: null
})

const platforms = [
  { label: 'Windows', value: 'windows', icon: 'pi-microsoft' },
  { label: 'Linux', value: 'linux', icon: 'pi-server' }
]

const generated = ref(null)
const showRawToken = ref(false)

watch(
  () => props.visible,
  (val) => {
    if (val) {
      reset()
    }
  }
)

function reset() {
  step.value = 1
  loading.value = false
  errorMessage.value = ''
  showRawToken.value = false
  generated.value = null
  form.value = {
    name: '',
    platform_hint: 'windows',
    expires_in_days: null
  }
}

function close() {
  emit('update:visible', false)
  if (generated.value) {
    emit('created')
  }
}

async function handleCreate() {
  errorMessage.value = ''
  if (!form.value.name.trim()) {
    errorMessage.value = 'Dê um nome ao agente (ex: DESKTOP-RH-Joao)'
    return
  }

  loading.value = true
  try {
    const response = await agentTokensApi.create({
      name: form.value.name.trim(),
      platform_hint: form.value.platform_hint,
      expires_in_days: form.value.expires_in_days
    })
    generated.value = response.data
    step.value = 2
  } catch (err) {
    errorMessage.value =
      err.response?.data?.detail || 'Erro ao gerar token'
  } finally {
    loading.value = false
  }
}

async function copyToClipboard(text, label) {
  try {
    await navigator.clipboard.writeText(text)
    toast.add({
      severity: 'success',
      summary: 'Copiado',
      detail: `${label} copiado pra área de transferência`,
      life: 2000
    })
  } catch (e) {
    toast.add({
      severity: 'warn',
      summary: 'Falha ao copiar',
      detail: 'Selecione manualmente o texto',
      life: 3000
    })
  }
}
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :modal="true"
    :closable="step === 1"
    :close-on-escape="step === 1"
    :style="{ width: '600px' }"
    :header="step === 1 ? 'Adicionar novo agente' : 'Agente gerado!'"
  >
    <!-- PASSO 1: formulário -->
    <div v-if="step === 1" class="form-step">
      <p class="text-muted">
        Preencha as informações abaixo. Um token único será gerado para esta
        máquina específica.
      </p>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>

      <div class="field">
        <label for="agent-name">Nome do agente</label>
        <InputText
          id="agent-name"
          v-model="form.name"
          placeholder="DESKTOP-RH-Joao"
          fluid
          autofocus
        />
        <small class="text-muted">
          Use o hostname da máquina ou um identificador único.
        </small>
      </div>

      <div class="field">
        <label for="agent-platform">Plataforma</label>
        <Select
          id="agent-platform"
          v-model="form.platform_hint"
          :options="platforms"
          option-label="label"
          option-value="value"
          fluid
        >
          <template #option="{ option }">
            <div class="platform-option">
              <i :class="['pi', option.icon]"></i>
              <span>{{ option.label }}</span>
            </div>
          </template>
        </Select>
      </div>

      <div class="field">
        <label for="agent-expires">Validade (dias)</label>
        <InputNumber
          id="agent-expires"
          v-model="form.expires_in_days"
          placeholder="Deixe vazio para nunca expirar"
          :min="1"
          :max="3650"
          fluid
        />
        <small class="text-muted">
          Opcional. Tokens com prazo são mais seguros, mas precisam ser
          renovados.
        </small>
      </div>
    </div>

    <!-- PASSO 2: token gerado + comando -->
    <div v-else-if="step === 2 && generated" class="result-step">
      <Message severity="warn" :closable="false">
        <strong>Importante:</strong> este token será mostrado apenas uma vez.
        Anote ou copie agora.
      </Message>

      <div class="field">
        <label>Token gerado</label>
        <div class="token-row">
          <InputText
            :model-value="
              showRawToken
                ? generated.raw_token
                : '•••••••••••••••••••••••••••••••••••••'
            "
            readonly
            fluid
            class="mono"
          />
          <Button
            :icon="showRawToken ? 'pi pi-eye-slash' : 'pi pi-eye'"
            outlined
            @click="showRawToken = !showRawToken"
            :aria-label="showRawToken ? 'Ocultar' : 'Mostrar'"
          />
          <Button
            icon="pi pi-copy"
            outlined
            @click="copyToClipboard(generated.raw_token, 'Token')"
            aria-label="Copiar token"
          />
        </div>
      </div>

      <div class="field">
        <label>Comando one-liner para a máquina-alvo</label>
        <div class="command-block">
          <Textarea
            :model-value="generated.install_command_oneliner"
            readonly
            rows="3"
            class="mono"
            fluid
            auto-resize
          />
          <Button
            icon="pi pi-copy"
            label="Copiar"
            outlined
            @click="
              copyToClipboard(generated.install_command_oneliner, 'Comando')
            "
          />
        </div>
        <small class="text-muted">
          <Tag
            v-if="generated.platform_hint === 'windows'"
            severity="info"
            value="PowerShell como admin"
          />
          <Tag
            v-else
            severity="info"
            value="Bash com sudo"
          />
          Cole este comando na máquina-alvo. Ele baixa, instala e inicia o
          agente como serviço.
        </small>
      </div>

      <div class="info-box">
        <i class="pi pi-info-circle"></i>
        <div>
          <strong>O que vai acontecer:</strong>
          <ol>
            <li>Script baixa o binário do GitHub Releases</li>
            <li>Instala em <code>{{ generated.platform_hint === 'windows' ? 'C:\\Program Files\\SolloRMM' : '/opt/sollorm' }}</code></li>
            <li>Cria serviço {{ generated.platform_hint === 'windows' ? 'Windows' : 'systemd' }} que inicia automaticamente</li>
            <li>Agente aparece no dashboard em ~30 segundos</li>
          </ol>
        </div>
      </div>
    </div>

    <template #footer>
      <div v-if="step === 1" class="footer-actions">
        <Button label="Cancelar" outlined @click="close" />
        <Button
          :label="loading ? 'Gerando...' : 'Gerar token'"
          icon="pi pi-key"
          :loading="loading"
          @click="handleCreate"
        />
      </div>
      <div v-else class="footer-actions">
        <Button label="Fechar" @click="close" />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
.form-step,
.result-step {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field label {
  font-size: 0.85rem;
  font-weight: 500;
}

.field small {
  margin-top: 0.25rem;
}

.platform-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.token-row {
  display: flex;
  gap: 0.5rem;
  align-items: stretch;
}

.token-row :deep(.p-inputtext) {
  flex: 1;
}

.command-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.mono {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.85rem;
}

.info-box {
  background: var(--p-surface-100);
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  gap: 0.75rem;
  font-size: 0.9rem;
}

.sollorm-dark .info-box {
  background: var(--p-surface-800);
}

.info-box i {
  color: var(--p-primary-color);
  margin-top: 0.2rem;
}

.info-box ol {
  margin: 0.4rem 0 0 1rem;
  padding: 0;
}

.info-box li {
  margin: 0.25rem 0;
}

.info-box code {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.8rem;
  background: var(--p-content-background);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}

.footer-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
