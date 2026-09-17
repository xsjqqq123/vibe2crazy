import { describe, it, expect } from 'vitest'
import { extractHeadings, extractHeadingText, slugify } from '../markdownHeadings'

describe('slugify', () => {
  it('lowercases and hyphenates', () => {
    expect(slugify('Hello World')).toBe('hello-world')
  })

  it('preserves CJK', () => {
    expect(slugify('架构设计')).toBe('架构设计')
  })

  it('strips punctuation', () => {
    expect(slugify('What is it?!!')).toBe('what-is-it')
  })

  it('collapses repeated separators', () => {
    expect(slugify('a  --  b')).toBe('a-b')
  })
})

describe('extractHeadingText', () => {
  it('removes bold, italic, code, links and html', () => {
    expect(extractHeadingText('**bold** and `code`')).toBe('bold and code')
    expect(extractHeadingText('[label](https://x.com)')).toBe('label')
    expect(extractHeadingText('<span>tagged</span>')).toBe('tagged')
  })
})

describe('extractHeadings', () => {
  it('returns headings with level, text and anchor', () => {
    const headings = extractHeadings('# One\n\ntext\n\n## Two\n\n### Three')
    expect(headings).toEqual([
      { level: 1, text: 'One', anchorId: 'one' },
      { level: 2, text: 'Two', anchorId: 'two' },
      { level: 3, text: 'Three', anchorId: 'three' }
    ])
  })

  it('ignores hash characters that are not headings', () => {
    expect(extractHeadings('#nospace\ncode # inside')).toEqual([])
  })

  it('stops at level six', () => {
    expect(extractHeadings('####### seven').length).toBe(0)
  })

  it('returns nothing for empty content', () => {
    expect(extractHeadings('')).toEqual([])
  })

  it('agrees with the anchor the renderer writes', () => {
    // MarkdownRenderer sets the same slug via installHeadingAnchors.
    expect(extractHeadings('## Hello World')[0].anchorId).toBe(slugify('Hello World'))
  })
})
