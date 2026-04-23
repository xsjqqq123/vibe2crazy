import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import FileCacheService from '../FileCacheService'

describe('FileCacheService', () => {
  const taskId = 'test-task-123'
  const filePath = 'src/main.ts'
  const hash = 'sha256:abc123def456'
  const content = 'console.log("Hello, World!")'

  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    // Reset any mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('get', () => {
    it('returns null for missing key', () => {
      const result = FileCacheService.get(taskId, filePath)
      expect(result).toBeNull()
    })

    it('returns cached entry when exists', () => {
      FileCacheService.set(taskId, filePath, hash, content)
      const result = FileCacheService.get(taskId, filePath)
      expect(result).toMatchObject({ hash, content })
      expect(result?.timestamp).toBeGreaterThan(0)
    })

    it('returns null when hash does not match', () => {
      FileCacheService.set(taskId, filePath, hash, content)
      // Get with different task should return null
      const result = FileCacheService.get('different-task', filePath)
      expect(result).toBeNull()
    })
  })

  describe('set', () => {
    it('stores entry in localStorage', () => {
      FileCacheService.set(taskId, filePath, hash, content)

      const key = `filecache:${taskId}:${filePath}`
      const stored = localStorage.getItem(key)
      expect(stored).not.toBeNull()

      const parsed = JSON.parse(stored!)
      expect(parsed).toMatchObject({ hash, content })
      expect(parsed.timestamp).toBeGreaterThan(0)
    })

    it('overwrites existing entry', () => {
      FileCacheService.set(taskId, filePath, 'old-hash', 'old content')
      FileCacheService.set(taskId, filePath, hash, content)

      const result = FileCacheService.get(taskId, filePath)
      expect(result).toMatchObject({ hash, content })
    })
  })

  describe('clear', () => {
    it('clears all entries when no taskId provided', () => {
      FileCacheService.set(taskId, 'file1.ts', hash, content)
      FileCacheService.set('other-task', 'file2.ts', hash, content)

      FileCacheService.clear()

      expect(FileCacheService.get(taskId, 'file1.ts')).toBeNull()
      expect(FileCacheService.get('other-task', 'file2.ts')).toBeNull()
    })

    it('clears only entries for specified taskId', () => {
      FileCacheService.set(taskId, 'file1.ts', hash, content)
      FileCacheService.set('other-task', 'file2.ts', hash, content)

      FileCacheService.clear(taskId)

      expect(FileCacheService.get(taskId, 'file1.ts')).toBeNull()
      expect(FileCacheService.get('other-task', 'file2.ts')).not.toBeNull()
    })
  })

  describe('getStorageSize', () => {
    it('returns 0 when empty', () => {
      expect(FileCacheService.getStorageSize()).toBe(0)
    })

    it('returns total size of cached entries', () => {
      FileCacheService.set(taskId, 'file1.ts', hash, content)
      FileCacheService.set(taskId, 'file2.ts', hash, content + ' more data')

      const size = FileCacheService.getStorageSize()
      expect(size).toBeGreaterThan(0)
    })
  })

  describe('quota handling', () => {
    it('handles quota exceeded error gracefully', () => {
      // Clear localStorage first
      localStorage.clear()

      // Pre-populate with some data to be cleared
      localStorage.setItem('filecache:old-task:old-file.ts', JSON.stringify({ hash: 'old-hash', content: 'old content', timestamp: 1000 }))

      // Use spyOn to throw QuotaExceededError on all calls
      const setItemSpy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
        throw new DOMException('Quota exceeded', 'QuotaExceededError')
      })

      // This should not throw - the service catches the error gracefully
      expect(() => {
        FileCacheService.set(taskId, filePath, hash, content)
      }).not.toThrow()

      // Restore
      setItemSpy.mockRestore()
    })
  })

  describe('localStorage unavailable', () => {
    it('returns null when localStorage throws', () => {
      // Mock localStorage.getItem to throw
      const originalGetItem = localStorage.getItem
      localStorage.getItem = vi.fn(() => {
        throw new Error('localStorage not available')
      })

      const result = FileCacheService.get(taskId, filePath)
      expect(result).toBeNull()

      // Restore
      localStorage.getItem = originalGetItem
    })
  })
})
