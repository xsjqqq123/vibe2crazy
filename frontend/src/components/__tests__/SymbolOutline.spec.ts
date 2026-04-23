// frontend/src/components/__tests__/SymbolOutline.spec.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SymbolOutline from '../Monaco/SymbolOutline.vue'
import type { SymbolInfo } from '@/composables/useSymbolOutline'

describe('SymbolOutline', () => {
  const mockSymbols: SymbolInfo[] = [
    { name: 'hello', kind: 'function', lineNumber: 1 },
    { name: 'UserService', kind: 'class', lineNumber: 5 },
    { name: 'config', kind: 'variable', lineNumber: 10 },
    { name: 'API_URL', kind: 'constant', lineNumber: 15 },
    { name: 'vue', kind: 'import', lineNumber: 1 },
  ]

  it('renders all symbols when not collapsed', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false, previewCollapsed: true }
    })

    expect(wrapper.text()).toContain('hello')
    expect(wrapper.text()).toContain('UserService')
    expect(wrapper.text()).toContain('config')
    expect(wrapper.text()).toContain('API_URL')
  })

  it('shows symbol count in header', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false, previewCollapsed: true }
    })

    expect(wrapper.text()).toContain('5')
  })

  it('hides symbols when collapsed', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: true, previewCollapsed: true }
    })

    // Symbols should not be visible in collapsed state
    const tags = wrapper.findAll('.symbol-tag')
    expect(tags.length).toBe(0)
  })

  it('emits select event when symbol is clicked', async () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false, previewCollapsed: true }
    })

    const firstTag = wrapper.find('.symbol-tag')
    await firstTag.trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0][0]).toEqual(mockSymbols[0])
  })

  it('emits toggle event when collapse button is clicked', async () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false, previewCollapsed: true }
    })

    const toggleBtn = wrapper.find('.outline-toggle')
    await toggleBtn.trigger('click')

    expect(wrapper.emitted('toggle')).toBeTruthy()
  })

  it('shows "No symbols found" message when empty', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: [], collapsed: false, previewCollapsed: true }
    })

    expect(wrapper.text()).toContain('No symbols')
  })

  it('applies correct color class for function symbols', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: [{ name: 'test', kind: 'function', lineNumber: 1 }], collapsed: false, previewCollapsed: true }
    })

    const tag = wrapper.find('.symbol-tag')
    expect(tag.classes()).toContain('symbol-function')
  })

  it('applies correct color class for class symbols', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: [{ name: 'Test', kind: 'class', lineNumber: 1 }], collapsed: false, previewCollapsed: true }
    })

    const tag = wrapper.find('.symbol-tag')
    expect(tag.classes()).toContain('symbol-class')
  })

  it('shows expand icon when collapsed', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: true, previewCollapsed: true }
    })

    expect(wrapper.find('.outline-toggle').text()).toContain('▶')
  })

  it('shows collapse icon when expanded', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false, previewCollapsed: true }
    })

    expect(wrapper.find('.outline-toggle').text()).toContain('▼')
  })
})