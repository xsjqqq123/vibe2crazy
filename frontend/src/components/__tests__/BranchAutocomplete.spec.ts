import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import BranchAutocomplete from '../BranchAutocomplete.vue'
import { getBranches } from '@/api/git'

vi.mock('@/api/git', () => ({
  getBranches: vi.fn()
}))

describe('BranchAutocomplete', () => {
  it('renders input field with placeholder', () => {
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '', placeholder: 'Select branch' }
    })
    expect(wrapper.find('input').attributes('placeholder')).toBe('Select branch')
  })

  it('emits update:modelValue when input changes', async () => {
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '' }
    })
    const input = wrapper.find('input')
    await input.setValue('main')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual(['main'])
  })

  it('loads branches when gitPath changes to valid value', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop', 'feature-x'],
      current_branch: 'main',
      success: true,
      message: null
    })
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '' }
    })
    await wrapper.setProps({ gitPath: '/path/to/repo' })
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(mockGetBranches).toHaveBeenCalledWith('/path/to/repo')
  })

  it('auto-fills current branch on successful load when modelValue is empty', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop'],
      current_branch: 'main',
      success: true,
      message: null
    })
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '' }
    })
    await wrapper.setProps({ gitPath: '/path/to/repo' })
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual(['main'])
  })

  it('does not auto-fill when modelValue already has value', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop'],
      current_branch: 'main',
      success: true,
      message: null
    })
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: 'develop', gitPath: '' }
    })
    await wrapper.setProps({ gitPath: '/path/to/repo' })
    await new Promise(resolve => setTimeout(resolve, 100))
    const emitted = wrapper.emitted('update:modelValue')
    if (emitted) {
      expect(emitted[emitted.length - 1]).not.toEqual(['main'])
    }
  })

  it('shows dropdown when button is clicked and branches exist', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: ['main', 'develop'],
      current_branch: 'main',
      success: true,
      message: null
    })
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '/repo' }
    })
    await new Promise(resolve => setTimeout(resolve, 100))
    const dropdownBtn = wrapper.find('button')
    await dropdownBtn.trigger('click')
    expect(wrapper.html()).toContain('main')
  })

  it('disables dropdown button when no branches available', async () => {
    const mockGetBranches = vi.mocked(getBranches)
    mockGetBranches.mockResolvedValue({
      branches: [],
      current_branch: '',
      success: false,
      message: 'Not a git repo'
    })
    const wrapper = mount(BranchAutocomplete, {
      props: { modelValue: '', gitPath: '/non-repo' }
    })
    await new Promise(resolve => setTimeout(resolve, 100))
    const dropdownBtn = wrapper.find('button')
    expect(dropdownBtn.attributes('disabled')).toBeDefined()
  })
})