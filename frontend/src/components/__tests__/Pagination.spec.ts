import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Pagination from '../Pagination.vue'

describe('Pagination', () => {
  it('disables Previous button on first page', () => {
    const wrapper = mount(Pagination, {
      props: {
        total: 100,
        page: 1,
        pageSize: 30,
        totalPages: 4
      }
    })

    const prevBtn = wrapper.findAll('button')[0]
    expect(prevBtn.attributes('disabled')).toBeDefined()
  })

  it('disables Next button on last page', () => {
    const wrapper = mount(Pagination, {
      props: {
        total: 100,
        page: 4,
        pageSize: 30,
        totalPages: 4
      }
    })

    const buttons = wrapper.findAll('button')
    const nextBtn = buttons[buttons.length - 1]
    expect(nextBtn.attributes('disabled')).toBeDefined()
  })

  it('emits page-change when clicking page number', async () => {
    const wrapper = mount(Pagination, {
      props: {
        total: 100,
        page: 1,
        pageSize: 30,
        totalPages: 4
      }
    })

    // Click page 2 button (index 2: Previous=0, Page1=1, Page2=2)
    const pageBtn = wrapper.findAll('button')[2]
    await pageBtn.trigger('click')

    expect(wrapper.emitted('page-change')).toBeTruthy()
    expect(wrapper.emitted('page-change')![0]).toEqual([2])
  })

  it('shows ellipsis for large page counts', () => {
    const wrapper = mount(Pagination, {
      props: {
        total: 300,
        page: 5,
        pageSize: 30,
        totalPages: 10
      }
    })

    expect(wrapper.text()).toContain('...')
  })

  it('shows correct range display', () => {
    const wrapper = mount(Pagination, {
      props: {
        total: 100,
        page: 2,
        pageSize: 30,
        totalPages: 4
      }
    })

    expect(wrapper.text()).toContain('Showing 31-60 of 100 commits')
  })

  it('handles empty state gracefully', () => {
    const wrapper = mount(Pagination, {
      props: {
        total: 0,
        page: 1,
        pageSize: 30,
        totalPages: 0
      }
    })

    // When totalPages is 0, the component shows nothing (v-if="totalPages > 0")
    expect(wrapper.text()).toBe('')
  })
})
