import request from './client'

export interface DirectoryListResponse {
  directories: string[]
}

const filesystemApi = {
  listDirectories: (path: string) =>
    request<DirectoryListResponse>(`/filesystem/directories?path=${encodeURIComponent(path)}`)
}

export default filesystemApi
