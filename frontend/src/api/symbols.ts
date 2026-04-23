import request from './client'

export interface IndexProgress {
  files_scanned: number
  total_files: number
  symbols_found: number
}

export interface IndexResponse {
  job_id: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  message?: string
  cached: boolean
  indexed_files?: number
  indexed_symbols?: number
  duration_seconds?: number
  error?: string
  suggestion?: string
  progress?: IndexProgress
}

export interface SymbolMatchItem {
  file_path: string
  line_number: number
  kind: string
  signature?: string
  is_header?: boolean
}

export interface SymbolDefinitionResponse {
  found: boolean
  name?: string
  kind?: string
  file_path?: string
  line_number?: number
  type_signature?: string
  signature_file_path?: string
  signature_line_number?: number
  docstring?: string
  definition_snippet?: string[]
  snippet_highlight_index?: number
  reason?: string
  message?: string
  similar_symbols?: string[]
  matches?: SymbolMatchItem[]
}

/**
 * Start an asynchronous indexing job for the project
 */
export async function startIndexJob(
  taskId: string,
  force: boolean = false
): Promise<IndexResponse> {
  return request<IndexResponse>('/symbols/index', {
    method: 'POST',
    body: JSON.stringify({ task_id: taskId, force })
  })
}

/**
 * Get the status of an indexing job
 */
export async function getIndexStatus(jobId: string): Promise<IndexResponse> {
  return request<IndexResponse>(`/symbols/index/status?job_id=${encodeURIComponent(jobId)}`)
}

/**
 * Get symbol definition details
 */
export async function getSymbolDefinition(
  symbolName: string,
  filePath: string,
  taskId: string
): Promise<SymbolDefinitionResponse> {
  const params = new URLSearchParams({
    symbol_name: symbolName,
    file_path: filePath,
    task_id: taskId
  })
  return request<SymbolDefinitionResponse>(`/symbols/definition?${params}`)
}

/**
 * Get symbol details at a specific location
 */
export async function getSymbolDetail(
  filePath: string,
  lineNumber: number,
  taskId: string
): Promise<SymbolDefinitionResponse> {
  const params = new URLSearchParams({
    file_path: filePath,
    line_number: lineNumber.toString(),
    task_id: taskId
  })
  return request<SymbolDefinitionResponse>(`/symbols/detail?${params}`)
}

export const symbolsApi = {
  startIndexJob,
  getIndexStatus,
  getSymbolDefinition,
  getSymbolDetail
}
