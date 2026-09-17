import request from './client'

export interface NotebookGroup {
  id: string
  name: string
  position: number
  is_default: boolean
  note_count: number
}

export interface Notebook {
  id: string
  title: string
  filename: string
  group_id: string
  position: number
  pinned: boolean
  size: number
  /** Epoch seconds, for display only. */
  mtime: number | null
}

export interface NotebookDetail extends Notebook {
  content: string
  group_name: string
  /** Optimistic-lock token. Echo back as `baseHash` when saving. */
  hash: string | null
}

export interface NotebookTreeGroup {
  id: string
  name: string
  position: number
  is_default: boolean
  note_count: number
  notes: Notebook[]
}

export interface NotebookTree {
  root: string
  groups: NotebookTreeGroup[]
}

export interface NotebookContentResult {
  id: string
  size: number
  mtime: number
  /** The token to send on the next save. */
  hash: string
}

export interface NotebookSearchResult {
  id: string
  title: string
  filename: string
  group_name: string
  match_type: 'filename' | 'content'
  snippet: string | null
  line: number | null
}

export interface NotebookSearchResponse {
  query: string
  results: NotebookSearchResult[]
  total: number
  truncated: boolean
}

export type MoveDirection = 'up' | 'down'

const notebooksApi = {
  // -- groups --
  createGroup: (name: string) =>
    request<NotebookGroup>('/notebooks/groups', {
      method: 'POST',
      body: JSON.stringify({ name })
    }),

  renameGroup: (groupId: string, name: string) =>
    request<NotebookGroup>(`/notebooks/groups/${groupId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name })
    }),

  deleteGroup: (groupId: string, force = false) =>
    request(`/notebooks/groups/${groupId}?force=${force}`, { method: 'DELETE' }),

  moveGroup: (groupId: string, direction: MoveDirection) =>
    request<NotebookGroup[]>(`/notebooks/groups/${groupId}/move`, {
      method: 'POST',
      body: JSON.stringify({ direction })
    }),

  // -- notes --
  tree: () => request<NotebookTree>('/notebooks'),

  get: (noteId: string) => request<NotebookDetail>(`/notebooks/${noteId}`),

  create: (groupId: string, title: string, content = '') =>
    request<NotebookDetail>('/notebooks', {
      method: 'POST',
      body: JSON.stringify({ group_id: groupId, title, content })
    }),

  update: (noteId: string, data: { title?: string; group_id?: string }) =>
    request<Notebook>(`/notebooks/${noteId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  /** Pass `baseHash` to be rejected with 409 if the file changed on disk. */
  saveContent: (noteId: string, content: string, baseHash: string | null = null) =>
    request<NotebookContentResult>(`/notebooks/${noteId}/content`, {
      method: 'PUT',
      body: JSON.stringify({ content, base_hash: baseHash })
    }),

  setPinned: (noteId: string, pinned: boolean) =>
    request<Notebook>(`/notebooks/${noteId}/pin`, {
      method: 'POST',
      body: JSON.stringify({ pinned })
    }),

  move: (noteId: string, direction: MoveDirection) =>
    request<Notebook[]>(`/notebooks/${noteId}/move`, {
      method: 'POST',
      body: JSON.stringify({ direction })
    }),

  remove: (noteId: string) => request(`/notebooks/${noteId}`, { method: 'DELETE' }),

  // -- search --
  search: (query: string, limit = 50) =>
    request<NotebookSearchResponse>(
      `/notebooks/search?q=${encodeURIComponent(query)}&limit=${limit}`
    )
}

export default notebooksApi
