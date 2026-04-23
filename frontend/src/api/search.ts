import request from './client'

export interface SearchMatch {
  file: string
  line: number
  content: string
}

export interface SearchResult {
  results: SearchMatch[]
  total: number
  cached: boolean
}

export interface SearchRequest {
  task_id: string
  query: string
  page?: number
  per_page?: number
}

const searchApi = {
  grep: (data: SearchRequest) =>
    request<SearchResult>('/search/grep', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  clearCache: (taskId: string) =>
    request<{ success: boolean }>('/search/cache', {
      method: 'DELETE'
    })
}

export default searchApi