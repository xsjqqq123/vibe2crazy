import request, { requestBlob, requestBlobWithProgress } from './client'

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileNode[]
}

export interface ChangedFileInfo {
  path: string
  status: 'A' | 'M' | 'D' | 'R' | 'C' | 'T' | '?' | 'U'
}

export interface PaginatedChangedFilesResponse {
  files: ChangedFileInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface FileUploadItem {
  filename: string
  success: boolean
  error?: string
}

export interface FileUploadResponse {
  success: boolean
  results: FileUploadItem[]
  total: number
  uploaded: number
  failed: number
}

export interface TempUploadResult {
  filename: string
  path: string
  size: number
  success: boolean
  error?: string
}

export interface TempUploadResponse {
  success: boolean
  results: TempUploadResult[]
  temp_dir: string
  total: number
  uploaded: number
  failed: number
}

type ProgressCallback = (progress: { loaded: number; total: number }) => void

const filesApi = {
  list: (taskId: string, path?: string) =>
    request<FileNode[]>(`/tasks/${taskId}/files${path ? `?path=${encodeURIComponent(path)}` : ''}`),

  read: (taskId: string, filePath: string) => {
    const encodedPath = filePath.split('/').map(encodeURIComponent).join('/')
    return request<{ content: string; hash: string | null }>(`/tasks/${taskId}/files/${encodedPath}`)
  },

  getHash: (taskId: string, filePath: string) => {
    const encodedPath = filePath.split('/').map(encodeURIComponent).join('/')
    return request<{ hash: string }>(`/tasks/${taskId}/files/${encodedPath}/hash`)
  },

  write: (taskId: string, filePath: string, content: string) =>
    request(`/tasks/${taskId}/files/${filePath}`, {
      method: 'PUT',
      body: JSON.stringify({ content })
    }),

  getChangedFiles: (taskId: string, page: number = 1, pageSize: number = 20) =>
    request<PaginatedChangedFilesResponse>(`/tasks/${taskId}/changed-files?page=${page}&page_size=${pageSize}`),

  getOriginal: (taskId: string, filePath: string) =>
    request<{ content: string }>(`/tasks/${taskId}/original/${filePath}`),

  getDiff: (taskId: string, filePath: string) =>
    request<{ diff: string }>(`/tasks/${taskId}/diff/${filePath}`),

  deleteFile: (taskId: string, filePath: string) =>
    request<{ success: boolean }>(`/tasks/${taskId}/files/${filePath}`, {
      method: 'DELETE'
    }),

  revertFile: (taskId: string, filePath: string) =>
    request<{ success: boolean; message: string; is_tracked: boolean }>(`/tasks/${taskId}/revert/${filePath}`, {
      method: 'POST'
    }),

  stageFile: (taskId: string, filePath: string) =>
    request<{ success: boolean; message: string }>(`/tasks/${taskId}/stage/${filePath}`, {
      method: 'POST'
    }),

  getRawFile: (taskId: string, filePath: string, onProgress?: ProgressCallback) => {
    const encodedPath = filePath.split('/').map(encodeURIComponent).join('/')
    if (onProgress) {
      return requestBlobWithProgress(`/tasks/${taskId}/files/${encodedPath}?raw=true`, onProgress)
    }
    return requestBlob(`/tasks/${taskId}/files/${encodedPath}?raw=true`)
  },

  searchFiles: (taskId: string, query: string = '', limit: number = 100) =>
    request<{ files: string[] }>(`/tasks/${taskId}/files/search?query=${encodeURIComponent(query)}&limit=${limit}`),

  uploadFiles: async (taskId: string, targetPath: string, files: FileList): Promise<FileUploadResponse> => {
    const formData = new FormData()
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i])
    }
    formData.append('target_path', targetPath)

    const token = localStorage.getItem('auth_token')
    const response = await fetch(`${import.meta.env.VITE_API_BASE || '/api'}/tasks/${taskId}/files/upload`, {
      method: 'POST',
      headers: {
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: formData
    })

    if (response.status === 401) {
      localStorage.removeItem('auth_token')
      const currentPath = window.location.pathname + window.location.search
      window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
      throw new Error('Unauthorized')
    }

    if (response.status === 403) {
      throw new Error('Forbidden')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
      throw new Error(error.detail || error.message || 'Upload failed')
    }

    return await response.json()
  },

  uploadToTemp: (
    taskId: string,
    files: File[],
    onProgress?: (progress: number, speed: string) => void
  ): Promise<TempUploadResponse> => {
    return new Promise((resolve, reject) => {
      const formData = new FormData()
      files.forEach(file => formData.append('files', file))

      const token = localStorage.getItem('auth_token')
      const xhr = new XMLHttpRequest()
      const startTime = Date.now()

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          const percentComplete = (e.loaded / e.total) * 100
          const timeElapsed = (Date.now() - startTime) / 1000
          const speed = e.loaded / timeElapsed
          const speedStr = speed > 1024 * 1024
            ? `${(speed / (1024 * 1024)).toFixed(1)} MB/s`
            : `${(speed / 1024).toFixed(1)} KB/s`
          onProgress(Math.round(percentComplete), speedStr)
        }
      }

      xhr.onload = () => {
        if (xhr.status === 401) {
          localStorage.removeItem('auth_token')
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
          reject(new Error('Unauthorized'))
          return
        }
        if (xhr.status >= 400) {
          try {
            const error = JSON.parse(xhr.responseText)
            reject(new Error(error.detail || 'Upload failed'))
          } catch {
            reject(new Error('Upload failed'))
          }
          return
        }
        resolve(JSON.parse(xhr.responseText))
      }

      xhr.onerror = () => reject(new Error('Network error'))
      xhr.ontimeout = () => reject(new Error('Upload timeout'))

      xhr.open('POST', `${import.meta.env.VITE_API_BASE || '/api'}/tasks/${taskId}/upload-temp`)
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.send(formData)
    })
  },

  downloadFile: (taskId: string, filePath: string) => {
    const token = localStorage.getItem('auth_token')
    const url = `${import.meta.env.VITE_API_BASE || '/api'}/tasks/${taskId}/files/${filePath}/download`
    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    // Create a link element and trigger download
    const link = document.createElement('a')
    link.href = url

    // Add auth header by using fetch with blob
    fetch(url, { headers })
      .then(response => {
        if (!response.ok) throw new Error('Download failed')
        return response.blob()
      })
      .then(blob => {
        const blobUrl = window.URL.createObjectURL(blob)
        link.href = blobUrl

        // Extract filename from path
        const filename = filePath.split('/').pop() || 'download'
        link.download = filename

        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(blobUrl)
      })
      .catch(error => {
        console.error('Download failed:', error)
        throw error
      })
  }
}

export default filesApi
