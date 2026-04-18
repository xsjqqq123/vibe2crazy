import request from './client'

export interface CommitFile {
  path: string
  status: 'A' | 'M' | 'D'
  additions: number
  deletions: number
}

export interface CommitInfo {
  hash: string
  date: string
  message: string
  files: CommitFile[]
}

export interface CommitFileItem {
  path: string
  status: 'A' | 'M' | 'D'
  additions: number
  deletions: number
}

export interface CommitDiff {
  hash: string
  date: string
  message: string
  files: CommitFileItem[]
  total_files: number
  page: number
  page_size: number
  total_pages: number
}

export interface FileDiff {
  path: string
  status: string
  original: string
  modified: string
}

export interface PaginatedCommitsResponse {
  items: CommitInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ResetResponse {
  success: boolean
  message: string
}

export interface BranchListResponse {
  branches: string[]
  current_branch: string
  success: boolean
  message: string | null
}

export async function getWorktreeCommits(
  taskId: string,
  page: number = 1,
  pageSize: number = 30
): Promise<PaginatedCommitsResponse> {
  return request<PaginatedCommitsResponse>(
    `/tasks/${taskId}/commits?page=${page}&page_size=${pageSize}`
  )
}

export async function getCommitDiff(
  taskId: string,
  commitHash: string,
  page: number = 1,
  pageSize: number = 20
): Promise<CommitDiff> {
  return request<CommitDiff>(
    `/tasks/${taskId}/commits/${commitHash}/diff?page=${page}&page_size=${pageSize}`
  )
}

export async function getFileDiff(
  taskId: string,
  commitHash: string,
  filePath: string
): Promise<FileDiff> {
  return request<FileDiff>(
    `/tasks/${taskId}/commits/${commitHash}/diff/files/${encodeURIComponent(filePath)}`
  )
}

export async function resetToCommit(
  taskId: string,
  commitHash: string,
  includeCommit: boolean = false
): Promise<ResetResponse> {
  return request<ResetResponse>(`/tasks/${taskId}/reset`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ commit_hash: commitHash, include_commit: includeCommit })
  })
}

export async function getBranches(gitPath: string): Promise<BranchListResponse> {
  return request<BranchListResponse>(`/git/branches?path=${encodeURIComponent(gitPath)}`)
}

export const gitApi = {
  getWorktreeCommits,
  getCommitDiff,
  getFileDiff,
  resetToCommit,
  getBranches
}
