import api from './client'

export const softwareApi = {
  list(agentId) {
    return api.get(`/agents/${agentId}/software`)
  },
}
