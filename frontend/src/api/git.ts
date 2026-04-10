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

export interface CommitFileDiff {
  path: string
  status: 'A' | 'M' | 'D'
  original: string
  modified: string
}

export interface CommitDiff {
  hash: string
  date: string
  message: string
  files: CommitFileDiff[]
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

export async function getCommitDiff(taskId: string, commitHash: string): Promise<CommitDiff> {
  return request<CommitDiff>(`/tasks/${taskId}/commits/${commitHash}/diff`)
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
  resetToCommit,
  getBranches
}
