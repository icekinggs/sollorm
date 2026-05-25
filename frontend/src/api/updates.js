import client from './client'

export default {
  status: () => client.get('/update-approvals/status'),
  list: () => client.get('/update-approvals'),
  create: (payload) => client.post('/update-approvals', payload),
  revoke: (id) => client.delete(`/update-approvals/${id}`),
}
