import request from './client'

export type TaskStatus = 'active' | 'completed' | 'merged'

export type TaskStatusType = 'running' | 'idle'
export type CodeStatusType = 'pending_review' | 'ready_to_merge' | 'no_changes'

export interface TaskStatusResponse {
  task_status: TaskStatusType
  code_status: CodeStatusType
  last_task_status_check?: string
  last_code_status_check?: string
}

export interface ButtonStatesResponse {
  can_accept: boolean
  can_merge: boolean
  reason?: string
}

export interface CommandExecution {
  command: string
  exit_code: number
  stdout: string
  stderr: string
  working_dir: string
}

export interface MergeResponse {
  success: boolean
  message: string
  conflicts?: string | null
  needs_resolution?: boolean  // NEW: Indicates sync has conflicts
  execution_log?: CommandExecution[]  // Detailed command execution log for debugging
}

export interface Task {
  id: string
  project_id: string
  name: string
  branch_name: string
  worktree_path: string
  tmux_session: string
  status: TaskStatus
  task_status: TaskStatusType
  code_status: CodeStatusType
  last_task_status_check?: string
  last_code_status_check?: string
  last_merge_commit_hash?: string
  extra_index_paths?: string
  direct_on_branch: boolean
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  name: string
  direct_on_branch?: boolean
}

export interface TaskUpdate {
  name?: string
  status?: TaskStatus
  extra_index_paths?: string
}

// Helper to determine if task is "completed"
export const isTaskCompleted = (task: Task): boolean => {
  return task.task_status === 'idle' && task.code_status === 'no_changes'
}

// Helper to get code status label/color
export const getCodeStatusLabel = (status: CodeStatusType) => {
  switch (status) {
    case 'pending_review': return { label: 'Pending review', color: 'text-yellow-600 dark:text-yellow-400' }
    case 'ready_to_merge': return { label: 'Ready to merge', color: 'text-blue-600 dark:text-blue-400' }
    case 'no_changes': return { label: 'No changes', color: 'text-gray-500 dark:text-gray-400' }
    default: return { label: 'Unknown', color: 'text-gray-400 dark:text-gray-400' }
  }
}

// Helper to get task status label/color
export const getTaskStatusLabel = (status: TaskStatusType) => {
  switch (status) {
    case 'running': return { label: 'Running', color: 'text-green-600 dark:text-green-400', icon: '🟢' }
    case 'idle': return { label: 'Idle', color: 'text-gray-500 dark:text-gray-400', icon: '⚪' }
    default: return { label: 'Unknown', color: 'text-gray-400 dark:text-gray-400', icon: '❓' }
  }
}

const tasksApi = {
  list: (projectId: string) =>
    request<Task[]>(`/projects/${projectId}/tasks`),

  get: (id: string) => request<Task>(`/tasks/${id}`),

  create: (projectId: string, data: TaskCreate) =>
    request<Task>(`/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  update: (projectId: string, taskId: string, data: TaskUpdate) =>
    request<Task>(`/projects/${projectId}/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  delete: (taskId: string) =>
    request('/tasks/' + taskId, {
      method: 'DELETE'
    }),

  accept: (taskId: string, message?: string) =>
    request('/tasks/' + taskId + '/accept', {
      method: 'POST',
      body: JSON.stringify({ message: message || 'Accept changes' })
    }),

  merge: (taskId: string, message: string = 'Merge task') =>
    request<MergeResponse>('/tasks/' + taskId + '/merge', {
      method: 'POST',
      body: JSON.stringify({ message })
    }),

  getStatus: (taskId: string): Promise<TaskStatusResponse> =>
    request<TaskStatusResponse>(`/tasks/${taskId}/status`),

  getButtonStates: (taskId: string): Promise<ButtonStatesResponse> =>
    request<ButtonStatesResponse>(`/tasks/${taskId}/button-states`)
}

export default tasksApi
