<script setup>
import { ref } from 'vue'
import Button from 'primevue/button'

const props = defineProps({
  url: { type: String, required: true },
  agentName: { type: String, default: '' },
})

const active = ref(false)
const iframeKey = ref(0)

function open() {
  iframeKey.value++
  active.value = true
}

function close() {
  active.value = false
}

function refresh() {
  iframeKey.value++
}
</script>

<template>
  <div class="mc-panel">
    <div v-if="!active" class="mc-placeholder">
      <div class="mc-info">
        <i class="pi pi-desktop mc-icon" />
        <div>
          <p class="mc-title">Remote Desktop via MeshCentral</p>
          <p class="mc-desc text-muted">
            Requer o agente MeshCentral instalado em <strong>{{ agentName }}</strong>.
            Após clicar, faça login no MeshCentral e selecione o dispositivo.
          </p>
        </div>
      </div>
      <Button label="Abrir Remote Desktop" icon="pi pi-external-link" @click="open" />
    </div>

    <div v-else class="mc-frame-wrapper">
      <div class="mc-toolbar">
        <span class="mc-toolbar-title">
          <i class="pi pi-desktop" />
          MeshCentral — {{ agentName }}
        </span>
        <div class="mc-toolbar-actions">
          <Button icon="pi pi-refresh" text rounded size="small" @click="refresh" aria-label="Recarregar" />
          <Button icon="pi pi-times" text rounded size="small" @click="close" aria-label="Fechar" />
        </div>
      </div>
      <iframe
        :key="iframeKey"
        :src="url"
        class="mc-iframe"
        allow="fullscreen clipboard-read clipboard-write"
        referrerpolicy="no-referrer-when-downgrade"
        title="MeshCentral Remote Desktop"
      />
    </div>
  </div>
</template>

<style scoped>
.mc-panel {
  display: flex;
  flex-direction: column;
}

.mc-placeholder {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mc-info {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.mc-icon {
  font-size: 2rem;
  color: var(--p-text-muted-color);
  margin-top: 0.1rem;
  flex-shrink: 0;
}

.mc-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.mc-desc {
  font-size: 0.875rem;
  line-height: 1.5;
}

.mc-frame-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.mc-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mc-toolbar-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--p-text-muted-color);
}

.mc-toolbar-actions {
  display: flex;
  gap: 0.25rem;
}

.mc-iframe {
  width: 100%;
  height: 620px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
}
</style>
