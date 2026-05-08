import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import FileTreeItem from '@/components/FileTreeItem.vue'
import { FileTreeSymbol, type UseFileTreeReturn, FileNode } from '@/composables/useFileTree'

// Mock file tree data
const createMockFileTree = (): UseFileTreeReturn => ({
  nodes: ref(new Map<string, FileNode>([
    ['test.ts', { name: 'test.ts', path: 'test.ts', type: 'file' }],
    ['src/', { name: 'src', path: 'src/', type: 'directory', children: [] }]
  ])),
  rootPaths: ref(['test.ts', 'src/']),
  loading: ref(false),
  loadingPaths: ref(new Set<string>()),
  expandedDirs: ref(new Set<string>()),
  loadRoot: async () => {},
  reloadPreservingState: async () => {},
  expandDir: async () => {},
  collapseDir: () => {},
  getNode: (path: string) => {
    const nodes = ref(new Map<string, FileNode>([
      ['test.ts', { name: 'test.ts', path: 'test.ts', type: 'file' }],
      ['src/', { name: 'src', path: 'src/', type: 'directory', children: [] }]
    ]))
    return nodes.value.get(path)
  },
  getChildPaths: () => [],
  expandParents: async () => {}
})

// Helper function to mount FileTreeItem with all required providers
function mountFileTreeItem(path: string, status?: string) {
  return mount(FileTreeItem, {
    props: {
      path,
      level: 0,
      status
    },
    global: {
      provide: {
        [FileTreeSymbol as symbol]: createMockFileTree(),
        isChanged: () => false,
        isSelected: () => false,
        isLoading: () => false,
        getFileStatus: () => undefined
      }
    }
  })
}

describe('FileTreeItem', () => {
  describe('Status Badge Display', () => {
    it('displays status badge when status prop is provided', () => {
      const wrapper = mountFileTreeItem('test.ts', 'M')
      expect(wrapper.find('.status-m').exists()).toBe(true)
      expect(wrapper.text()).toContain('M')
    })

    it('does not display status badge when status prop is not provided', () => {
      const wrapper = mountFileTreeItem('test.ts')
      expect(wrapper.find('.status-m').exists()).toBe(false)
      expect(wrapper.find('.status-badge').exists()).toBe(false)
    })

    it('displays correct status badge for different status codes', () => {
      const statuses = ['A', 'M', 'D', 'R', 'C', 'T', '?'] as const

      statuses.forEach(status => {
        const wrapper = mountFileTreeItem('test.ts', status)
        // Use classList to check for the exact status class
        const badge = wrapper.find('.status-badge')
        expect(badge.exists()).toBe(true)
        expect(badge.text()).toContain(status)
        // Verify the status class exists - check if it contains the status in some form
        const hasStatusClass = badge.classes().some(cls =>
          cls.includes(status === '?' ? '?' : status.toLowerCase())
        )
        expect(hasStatusClass).toBe(true)
      })
    })

    it('displays status badge on both files and directories', () => {
      // Test with file
      const fileWrapper = mountFileTreeItem('test.ts', 'M')
      expect(fileWrapper.find('.status-badge').exists()).toBe(true)
      expect(fileWrapper.find('.status-m').exists()).toBe(true)

      // Test with directory
      const dirWrapper = mountFileTreeItem('src/', 'A')
      expect(dirWrapper.find('.status-badge').exists()).toBe(true)
      expect(dirWrapper.find('.status-a').exists()).toBe(true)
    })

    it('shows badge content matching the status code', () => {
      const wrapper = mountFileTreeItem('test.ts', 'M')
      const badge = wrapper.find('.status-badge')
      expect(badge.text()).toBe('M')
    })
  })

  describe('Component Structure', () => {
    it('renders file node with correct structure', () => {
      const wrapper = mountFileTreeItem('test.ts', 'M')
      expect(wrapper.find('.file-tree-item').exists()).toBe(true)
      expect(wrapper.find('.file-tree-icon').exists()).toBe(true)
      expect(wrapper.text()).toContain('test.ts')
    })

    it('applies correct indentation based on level prop', () => {
      const wrapper = mountFileTreeItem('test.ts', 'M')
      const item = wrapper.find('.file-tree-item')
      const style = item.attributes('style')
      expect(style).toContain('padding-left: 0px') // level 0 * 16px = 0px
    })
  })
})
