declare module 'markdown-it-texmath' {
  import type MarkdownIt from 'markdown-it'

  const texmath: (md: MarkdownIt, options?: Record<string, unknown>) => void
  export default texmath
}