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
  }
}
