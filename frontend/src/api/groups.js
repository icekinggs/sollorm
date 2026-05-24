import api from './client'

export const groupsApi = {
  list() {
    return api.get('/groups')
  },

  create(payload) {
    return api.post('/groups', payload)
  },

  update(id, payload) {
    return api.put(`/groups/${id}`, payload)
  },

  remove(id) {
    return api.delete(`/groups/${id}`)
  },

  assignAgent(agentId, groupId) {
    return api.put(`/agents/${agentId}/group`, { group_id: groupId })
  },
}
