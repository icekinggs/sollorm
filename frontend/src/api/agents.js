import api from './client'

export const agentsApi = {
  list() {
    return api.get('/agents')
  },

  get(id) {
    return api.get(`/agents/${id}`)
  },

  heartbeats(id, limit = 100) {
    return api.get(`/agents/${id}/heartbeats`, { params: { limit } })
  },

  delete(id) {
    return api.delete(`/agents/${id}`)
  },

  executions(id, limit = 50) {
    return api.get(`/agents/${id}/executions`, { params: { limit } })
  },

  createExecution(id, payload) {
    return api.post(`/agents/${id}/executions`, payload)
  },

  patchScan(id) {
    return api.post(`/agents/${id}/patches/scan`)
  },

  patchGet(id) {
    return api.get(`/agents/${id}/patches`)
  },

  patchInstall(id, packageNames) {
    return api.post(`/agents/${id}/patches/install`, { package_names: packageNames })
  },

  patchInstallAll(id) {
    return api.post(`/agents/${id}/patches/install-all`)
  },

  update(id) {
    return api.post(`/agents/${id}/update`)
  }
}
