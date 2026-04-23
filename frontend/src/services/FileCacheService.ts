/**
 * Service for caching file content in localStorage with hash-based validation.
 *
 * Cache key format: filecache:{taskId}:{filePath}
 * Cache value: { hash: string, content: string, timestamp: number }
 */

const PREFIX = 'filecache:'

interface CachedEntry {
  hash: string
  content: string
  timestamp: number
}

class FileCacheService {
  /**
   * Get cached file entry.
   * Returns null if not found or on error.
   */
  get(taskId: string, filePath: string): CachedEntry | null {
    try {
      const key = this.buildKey(taskId, filePath)
      const stored = localStorage.getItem(key)
      if (!stored) return null

      const entry = JSON.parse(stored)
      // Validate entry structure
      if (typeof entry?.hash === 'string' && typeof entry?.content === 'string') {
        return { hash: entry.hash, content: entry.content, timestamp: entry.timestamp || 0 }
      }
      return null
    } catch {
      // localStorage not available or parse error
      return null
    }
  }

  /**
   * Store file content in cache.
   * Handles quota exceeded by clearing old entries.
   */
  set(taskId: string, filePath: string, hash: string, content: string): void {
    try {
      const key = this.buildKey(taskId, filePath)
      const value = JSON.stringify({ hash, content, timestamp: Date.now() })

      try {
        localStorage.setItem(key, value)
      } catch (e) {
        if (e instanceof DOMException && e.name === 'QuotaExceededError') {
          // Clear old entries and retry
          this.clearOldEntries()
          localStorage.setItem(key, value)
        } else {
          throw e
        }
      }
    } catch {
      // localStorage not available, skip caching
    }
  }

  /**
   * Clear all cached entries, or just for a specific task.
   */
  clear(taskId?: string): void {
    try {
      const keysToRemove: string[] = []

      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(PREFIX)) {
          if (taskId) {
            // Only clear entries for this task
            if (key.startsWith(`${PREFIX}${taskId}:`)) {
              keysToRemove.push(key)
            }
          } else {
            keysToRemove.push(key)
          }
        }
      }

      keysToRemove.forEach(key => localStorage.removeItem(key))
    } catch {
      // localStorage not available
    }
  }

  /**
   * Get total size of cached entries in bytes.
   */
  getStorageSize(): number {
    try {
      let totalSize = 0

      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(PREFIX)) {
          const value = localStorage.getItem(key)
          if (value) {
            // Rough estimate: each char is 2 bytes in UTF-16
            totalSize += (key.length + value.length) * 2
          }
        }
      }

      return totalSize
    } catch {
      return 0
    }
  }

  /**
   * Build cache key from taskId and filePath.
   */
  private buildKey(taskId: string, filePath: string): string {
    return `${PREFIX}${taskId}:${filePath}`
  }

  /**
   * Clear approximately 50% of cached entries (oldest first).
   * Used when quota is exceeded.
   */
  private clearOldEntries(): void {
    try {
      const entries: { key: string; timestamp: number }[] = []

      // Collect all cache entries with their timestamps
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(PREFIX)) {
          const stored = localStorage.getItem(key)
          if (stored) {
            try {
              const entry = JSON.parse(stored)
              entries.push({ key, timestamp: entry.timestamp || 0 })
            } catch {
              // Invalid entry, remove it
              entries.push({ key, timestamp: 0 })
            }
          }
        }
      }

      // Sort by timestamp (lower = older) and remove oldest 50%
      entries.sort((a, b) => a.timestamp - b.timestamp)
      const toRemove = entries.slice(0, Math.ceil(entries.length / 2))

      toRemove.forEach(entry => localStorage.removeItem(entry.key))
    } catch {
      // localStorage not available
    }
  }
}

// Export singleton instance
export default new FileCacheService()
