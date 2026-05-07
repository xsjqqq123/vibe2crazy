import { ref, Ref, inject, provide, InjectionKey } from 'vue'
import filesApi from '@/api/files'

// API response type (from files.ts)
interface ApiFileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: ApiFileNode[]
}

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: string[]      // Child paths (not node objects)
  expanded?: boolean        // Track expanded state
  loaded?: boolean          // Track if children loaded
  error?: boolean           // Error state
  errorMessage?: string     // Error message
}

export interface UseFileTreeReturn {
  nodes: Ref<Map<string, FileNode>>
  rootPaths: Ref<string[]>
  loading: Ref<boolean>
  loadingPaths: Ref<Set<string>>
  expandedDirs: Ref<Set<string>>
  loadRoot: () => Promise<void>
  expandDir: (path: string) => Promise<void>
  collapseDir: (path: string) => void
  getNode: (path: string) => FileNode | undefined
  getChildPaths: (path: string) => string[]
  expandParents: (filePath: string) => Promise<void>
}

// Convert API node to flattened FileNode
function toFileNode(apiNode: ApiFileNode): FileNode {
  return {
    name: apiNode.name,
    path: apiNode.path,
    type: apiNode.type,
    // Note: children array will be populated separately when loaded
    children: undefined,
    expanded: false,
    loaded: false,
    error: false
  }
}

export function useFileTree(taskId: Ref<string>): UseFileTreeReturn {
  const nodes = ref<Map<string, FileNode>>(new Map())
  const rootPaths = ref<string[]>([])
  const loading = ref(false)
  const loadingPaths = ref<Set<string>>(new Set())
  const expandedDirs = ref<Set<string>>(new Set())
  const collapsedDuringLoad = ref<Set<string>>(new Set())

  // Load top-level directories
  const loadRoot = async () => {
    loading.value = true
    const previousNodes = new Map(nodes.value)
    try {
      const tree = await filesApi.list(taskId.value)

      // Convert to flat structure
      nodes.value.clear()
      tree.forEach(node => {
        const fileNode = toFileNode(node)
        nodes.value.set(fileNode.path, fileNode)
      })
      rootPaths.value = tree.map(n => n.path)
    } catch (err: any) {
      nodes.value = previousNodes  // Restore on error
      console.error('Failed to load file tree:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  // Expand directory (lazy load children)
  const expandDir = async (path: string) => {
    // Prevent duplicate loads
    if (loadingPaths.value.has(path)) return

    const node = nodes.value.get(path)
    if (!node || node.type !== 'directory') return

    // Clear collapse intent when user explicitly expands
    collapsedDuringLoad.value.delete(path)

    // Load children if not already loaded
    if (!node.loaded) {
      loadingPaths.value.add(path)
      try {
        const children = await filesApi.list(taskId.value, path)

        // Add children to map
        children.forEach(child => {
          const fileNode = toFileNode(child)
          nodes.value.set(fileNode.path, fileNode)
        })

        // Update node with child paths - replace entire object for reactivity
        const childPaths = children.map(c => c.path)
        nodes.value.set(path, { ...node, children: childPaths, loaded: true, error: false })
      } catch (err: any) {
        console.error(`Failed to load directory ${path}:`, err)
        // Update error state - replace entire object for reactivity
        nodes.value.set(path, { ...node, error: true, errorMessage: err.message || 'Failed to load directory' })
      } finally {
        loadingPaths.value.delete(path)
      }
    }

    // Only mark as expanded if not collapsed during load
    if (!collapsedDuringLoad.value.has(path)) {
      expandedDirs.value.add(path)
    }
    collapsedDuringLoad.value.delete(path)
  }

  // Collapse directory
  const collapseDir = (path: string) => {
    expandedDirs.value.delete(path)
    // Track collapse intent during async load
    if (loadingPaths.value.has(path)) {
      collapsedDuringLoad.value.add(path)
    }
  }

  // Get node by path
  const getNode = (path: string): FileNode | undefined => {
    return nodes.value.get(path)
  }

  // Get child paths for a directory
  const getChildPaths = (path: string): string[] => {
    const node = nodes.value.get(path)
    return node?.type === 'directory' ? (node.children || []) : []
  }

  // Expand all parent directories of a file, making it visible in the tree
  const expandParents = async (filePath: string): Promise<void> => {
    if (!filePath) return

    // Extract all parent directory paths
    const parts = filePath.split('/')
    for (let i = 1; i < parts.length; i++) {
      const parentPath = parts.slice(0, i).join('/')
      const node = nodes.value.get(parentPath)
      if (node && node.type === 'directory' && !expandedDirs.value.has(parentPath)) {
        await expandDir(parentPath)
      }
    }
  }

  return {
    nodes,
    rootPaths,
    loading,
    loadingPaths,
    expandedDirs,
    loadRoot,
    expandDir,
    collapseDir,
    getNode,
    getChildPaths,
    expandParents
  }
}

// Provide/inject helpers for component tree
export const FileTreeSymbol: InjectionKey<UseFileTreeReturn> = Symbol('fileTree')

export function provideFileTree(tree: UseFileTreeReturn) {
  provide(FileTreeSymbol, tree)
}

export function injectFileTree() {
  const tree = inject(FileTreeSymbol)
  if (!tree) throw new Error('FileTree not provided')
  return tree
}
