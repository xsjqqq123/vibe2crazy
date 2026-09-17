import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import NotebookGroupNode from '../NotebookGroupNode.vue'
import type { Notebook, NotebookTreeGroup } from '@/api/notebooks'

const note = (over: Partial<Notebook> = {}): Notebook => ({
  id: 'n1',
  title: '笔记一',
  filename: '笔记一.md',
  group_id: 'g1',
  position: 1024,
  pinned: false,
  size: 10,
  mtime: 1,
  ...over
})

const group = (over: Partial<NotebookTreeGroup> = {}): NotebookTreeGroup => ({
  id: 'g1',
  name: '工作',
  position: 1024,
  is_default: false,
  note_count: 2,
  notes: [note(), note({ id: 'n2', title: '笔记二', filename: '笔记二.md', pinned: true })],
  ...over
})

const mountNode = (props: Partial<InstanceType<typeof NotebookGroupNode>['$props']> = {}) =>
  mount(NotebookGroupNode, {
    props: {
      group: group(),
      selectedId: null,
      collapsed: false,
      ...props
    }
  })

describe('NotebookGroupNode', () => {
  it('lists the notes when expanded', () => {
    const wrapper = mountNode()
    expect(wrapper.findAll('.note-item')).toHaveLength(2)
    expect(wrapper.text()).toContain('笔记一')
    expect(wrapper.text()).toContain('笔记二')
  })

  it('hides the notes when collapsed', () => {
    const wrapper = mountNode({ collapsed: true })
    // v-show keeps the nodes in the DOM but hides the container.
    expect(wrapper.find('.group-notes').isVisible()).toBe(false)
  })

  it('shows a pin icon only for pinned notes', () => {
    const wrapper = mountNode()
    const pinned = wrapper.findAll('.note-item').filter((n) => n.find('.pinned-icon').exists())
    expect(pinned).toHaveLength(1)
    expect(pinned[0].text()).toContain('笔记二')
  })

  it('marks the selected note', () => {
    const wrapper = mountNode({ selectedId: 'n2' })
    const items = wrapper.findAll('.note-item')
    expect(items[0].classes()).not.toContain('item-selected')
    expect(items[1].classes()).toContain('item-selected')
  })

  it('emits select with the note id', async () => {
    const wrapper = mountNode()
    await wrapper.findAll('.note-item')[1].trigger('click')
    expect(wrapper.emitted('select')![0]).toEqual(['n2'])
  })

  it('emits toggleCollapse when the header is clicked', async () => {
    const wrapper = mountNode()
    await wrapper.find('.group-header').trigger('click')
    expect(wrapper.emitted('toggleCollapse')![0]).toEqual(['g1'])
  })

  it('emits a note context menu with the event', async () => {
    const wrapper = mountNode()
    await wrapper.findAll('.note-item')[0].trigger('contextmenu')
    const payload = wrapper.emitted('noteContextMenu')![0][0] as any
    expect(payload.note.id).toBe('n1')
    expect(payload.event).toBeInstanceOf(Event)
  })

  it('emits a group context menu from the header', async () => {
    const wrapper = mountNode()
    await wrapper.find('.group-header').trigger('contextmenu')
    const payload = wrapper.emitted('groupContextMenu')![0][0] as any
    expect(payload.group.id).toBe('g1')
  })

  it('shows the note count', () => {
    const wrapper = mountNode()
    expect(wrapper.find('.group-header').text()).toContain('2')
  })

  it('shows an empty hint for a group with no notes', () => {
    const wrapper = mountNode({ group: group({ notes: [], note_count: 0 }) })
    expect(wrapper.findAll('.note-item')).toHaveLength(0)
    expect(wrapper.text()).toContain('Empty')
  })

  // The sidebar listens for contextmenu on its scroll container to offer the
  // "new note / new group" menu. Right-clicking a row must not also trigger it,
  // or the row menu is immediately overwritten.
  it('does not let a row context menu bubble to an ancestor', async () => {
    const onAncestorMenu = vi.fn()
    const wrapper = mount(
      {
        components: { NotebookGroupNode },
        setup: () => ({ group: group(), onAncestorMenu }),
        template: `<div class="ancestor" @contextmenu="onAncestorMenu">
                     <NotebookGroupNode :group="group" :selected-id="null" :collapsed="false" />
                   </div>`
      },
      { global: { components: { NotebookGroupNode } } }
    )

    await wrapper.find('.note-item').trigger('contextmenu')
    await wrapper.find('.group-header').trigger('contextmenu')

    expect(onAncestorMenu).not.toHaveBeenCalled()
    expect(wrapper.findComponent(NotebookGroupNode).emitted('noteContextMenu')).toBeTruthy()
    expect(wrapper.findComponent(NotebookGroupNode).emitted('groupContextMenu')).toBeTruthy()
  })
})
