import request from './client'

export interface QueueItem {
  id: string
  task_id: string
  content: string
  status: 'pending' | 'executing' | 'completed'
  created_at: string
  updated_at: string
  executed_at: string | null
}

const queueApi = {
  getQueue: (taskId: string) =>
    request<QueueItem[]>(`/tasks/${taskId}/queue`),

  addToQueue: (taskId: string, content: string) =>
    request<QueueItem>(`/tasks/${taskId}/queue`, {
      method: 'POST',
      body: JSON.stringify({ content })
    }),

  removeFromQueue: (taskId: string, messageId: string) =>
    request<void>(`/tasks/${taskId}/queue/${messageId}`, {
      method: 'DELETE'
    }),

  clearQueue: (taskId: string) =>
    request<void>(`/tasks/${taskId}/queue`, {
      method: 'DELETE'
    })
}

export default queueApi
