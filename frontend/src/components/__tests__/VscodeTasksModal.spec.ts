import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import VscodeTasksModal from '../VscodeTasksModal.vue'

const mountModal = (content: string, show = true) =>
  mount(VscodeTasksModal, {
    props: { show, filePath: '.vscode/tasks.json', content },
    // The component teleports to <body>; stubbing it keeps the markup inside
    // the wrapper so find() works.
    global: { stubs: { teleport: true, transition: false } }
  })

const FILE = JSON.stringify({
  version: '2.0.0',
  tasks: [{ label: 'build', type: 'shell', command: 'npm', args: ['run', 'build'] }]
})

const writeText = vi.fn().mockResolvedValue(undefined)
beforeEach(() => {
  writeText.mockClear()
  Object.assign(navigator, { clipboard: { writeText } })
})

describe('VscodeTasksModal', () => {
  it('renders nothing while hidden', () => {
    const wrapper = mountModal(FILE, false)
    expect(wrapper.find('.vt-overlay').exists()).toBe(false)
  })

  it('lists a task with both commands', () => {
    const wrapper = mountModal(FILE)
    expect(wrapper.findAll('.vt-task')).toHaveLength(1)
    const codes = wrapper.findAll('.vt-code').map((c) => c.text())
    expect(codes[0]).toBe('vtr build')
    expect(codes[1]).toContain('npm run build')
  })

  it('copies the vtr command', async () => {
    const wrapper = mountModal(FILE)
    await wrapper.findAll('.vt-copy')[0].trigger('click')
    expect(writeText).toHaveBeenCalledWith('vtr build')
  })

  it('copies the raw command from its own button', async () => {
    const wrapper = mountModal(FILE)
    await wrapper.findAll('.vt-copy')[1].trigger('click')
    expect(writeText).toHaveBeenCalledWith('npm run build')
  })

  it('confirms the copy on the button that was pressed', async () => {
    const wrapper = mountModal(FILE)
    const buttons = wrapper.findAll('.vt-copy')
    await buttons[0].trigger('click')
    expect(buttons[0].text()).toContain('Copied')
    expect(buttons[1].text()).toBe('Copy')
  })

  it('shows a parse error instead of rows', () => {
    const wrapper = mountModal('{ broken')
    expect(wrapper.findAll('.vt-task')).toHaveLength(0)
    expect(wrapper.find('.vt-notice-error').text()).toMatch(/Invalid JSON/)
  })

  it('shows an empty state when there are no tasks', () => {
    const wrapper = mountModal(JSON.stringify({ version: '2.0.0', tasks: [] }))
    expect(wrapper.find('.vt-notice').text()).toMatch(/No tasks/)
  })

  it('warns when the raw command needs shell variable expansion', () => {
    const wrapper = mountModal(
      JSON.stringify({ tasks: [{ label: 'x', command: 'node', args: ['${workspaceFolder}/a.js'] }] })
    )
    expect(wrapper.find('.vt-warn').text()).toMatch(/will not expand/)
  })

  it('lists dependsOn as metadata', () => {
    const wrapper = mountModal(
      JSON.stringify({ tasks: [{ label: 'ci', dependsOn: ['build', 'test'] }] })
    )
    expect(wrapper.find('.vt-meta').text()).toContain('Runs after: build, test')
    // A dependsOn-only task still gets a vtr command but no raw one.
    expect(wrapper.findAll('.vt-code')).toHaveLength(1)
  })

  it('emits close on Escape', async () => {
    const wrapper = mountModal(FILE)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits close when the backdrop is clicked', async () => {
    const wrapper = mountModal(FILE)
    await wrapper.find('.vt-overlay').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
