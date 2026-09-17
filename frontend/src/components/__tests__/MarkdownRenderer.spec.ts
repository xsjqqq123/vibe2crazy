import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownRenderer from '../MarkdownRenderer.vue'

const render = (content: string) => mount(MarkdownRenderer, { props: { content } })

describe('MarkdownRenderer', () => {
  it('renders headings as html', () => {
    const wrapper = render('# Hello World')
    const h1 = wrapper.find('h1')
    expect(h1.exists()).toBe(true)
    expect(h1.text()).toBe('Hello World')
  })

  it('adds a slug id to headings so the outline can scroll to them', () => {
    const wrapper = render('# Hello World')
    expect(wrapper.find('h1').attributes('id')).toBe('hello-world')
  })

  it('keeps CJK characters in heading anchors', () => {
    const wrapper = render('# 架构设计')
    expect(wrapper.find('h1').attributes('id')).toBe('架构设计')
  })

  it('highlights fenced code blocks with highlight.js', () => {
    const wrapper = render('```js\nconst a = 1;\n```')
    const pre = wrapper.find('pre.hljs')
    expect(pre.exists()).toBe(true)
    expect(pre.text()).toContain('const')
  })

  it('escapes unknown languages instead of throwing', () => {
    const wrapper = render('```notalanguage\n<b>raw</b>\n```')
    const pre = wrapper.find('pre.hljs')
    expect(pre.exists()).toBe(true)
    expect(pre.html()).toContain('&lt;b&gt;')
  })

  it('renders mermaid fences as a placeholder for the pane to hydrate', () => {
    const wrapper = render('```mermaid\ngraph TD; A-->B;\n```')
    const mermaid = wrapper.find('.mermaid')
    expect(mermaid.exists()).toBe(true)
    expect(mermaid.text()).toContain('graph TD')
  })

  it('renders gfm tables', () => {
    const wrapper = render('| a | b |\n| - | - |\n| 1 | 2 |')
    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.findAll('td').length).toBe(2)
  })

  it('shows an empty state for blank content', () => {
    const wrapper = render('')
    expect(wrapper.find('.md-empty').exists()).toBe(true)
  })

  it('renders inline code and links', () => {
    const wrapper = render('use `npm run dev` and see [docs](https://example.com)')
    expect(wrapper.find('code').text()).toBe('npm run dev')
    expect(wrapper.find('a').attributes('href')).toBe('https://example.com')
  })
})
