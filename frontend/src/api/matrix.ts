import request from './client'
import type { MatrixTask } from '@/store/matrixStore'

interface TasksAllResponse {
  tasks: MatrixTask[]
}

interface MatrixSessionInfo {
  index: number
  session_name: string
  exists: boolean
}

interface MatrixSessionsResponse {
  sessions: MatrixSessionInfo[]
}

interface MatrixSessionsRequest {
  count: number
}

const matrixApi = {
  async getAllTasks(): Promise<MatrixTask[]> {
    const response = await request<TasksAllResponse>('/tasks/all')
    return response.tasks
  },

  async createSessions(count: number): Promise<MatrixSessionInfo[]> {
    const response = await request<MatrixSessionsResponse>('/matrix/sessions', {
      method: 'POST',
      body: JSON.stringify({ count } as MatrixSessionsRequest)
    })
    return response.sessions
  }
}

export default matrixApi