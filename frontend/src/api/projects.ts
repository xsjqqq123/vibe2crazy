import request from './client'

export interface Project {
  id: string
  name: string
  git_path: string
  main_branch: string
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  git_path: string
  main_branch?: string
  init_git?: boolean
  create_directory?: boolean
}

export interface ProjectUpdate {
  name?: string
  main_branch?: string
}

const projectsApi = {
  list: () => request<Project[]>('/projects'),

  get: (id: string) => request<Project>(`/projects/${id}`),

  create: (data: ProjectCreate) =>
    request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  update: (id: string, data: ProjectUpdate) =>
    request<Project>(`/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  delete: (id: string) =>
    request('/projects/' + id, {
      method: 'DELETE'
    })
}

export default projectsApi
