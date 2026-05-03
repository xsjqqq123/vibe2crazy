import request from './client'

export interface SearchMatch {
  file: string
  line: number
  content: string
}

export interface SearchResult {
  results: SearchMatch[]
  total: number  // 文件数（用于分页）
  total_matches: number  // 匹配数（用于显示）
  cached: boolean
}

export interface SearchRequest {
  task_id: string
  query: string
  page?: number
  per_page?: number
  current_file?: string
}

const searchApi = {
  grep: (data: SearchRequest) =>
    request<SearchResult>('/search/grep', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  clearCache: (taskId: string) =>
    request<{ success: boolean }>(`/search/cache?task_id=${encodeURIComponent(taskId)}`, {
      method: 'DELETE'
    })
}

export default searchApi