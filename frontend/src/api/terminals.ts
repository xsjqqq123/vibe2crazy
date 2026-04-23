import request from './client'

const terminalsApi = {
  getHistory: (taskId: string) =>
    request<string>(`/terminals/${taskId}/history`),

  getHistoryAsText: async (taskId: string): Promise<string> => {
    const token = localStorage.getItem('auth_token')
    const response = await fetch(`/api/terminals/${taskId}/history`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || error.message || 'Request failed')
    }

    return response.text()
  }
}

export default terminalsApi
