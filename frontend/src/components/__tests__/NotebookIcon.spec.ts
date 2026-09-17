import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import NotebookIcon from '../NotebookIcon.vue'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push })
}))

describe('NotebookIcon', () => {
  it('renders a labelled button', () => {
    const wrapper = mount(NotebookIcon)
    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
    expect(button.attributes('title')).toBe('Markdown Notebook')
  })

  it('navigates to the notebook route on click', async () => {
    push.mockClear()
    const wrapper = mount(NotebookIcon)
    await wrapper.find('button').trigger('click')
    expect(push).toHaveBeenCalledWith('/notebook')
  })
})
