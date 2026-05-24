import api from './client'

export const alertsApi = {
  listRules() {
    return api.get('/alert-rules')
  },

  createRule(payload) {
    return api.post('/alert-rules', payload)
  },

  updateRule(id, payload) {
    return api.put(`/alert-rules/${id}`, payload)
  },

  removeRule(id) {
    return api.delete(`/alert-rules/${id}`)
  },

  listEvents(params = {}) {
    return api.get('/alerts', { params })
  },

  listAgentEvents(agentId, params = {}) {
    return api.get(`/agents/${agentId}/alerts`, { params })
  },
}
