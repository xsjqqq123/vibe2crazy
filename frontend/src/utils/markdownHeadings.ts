/**
 * Heading extraction shared by the markdown renderer and the outline sidebar.
 *
 * Both sides must agree on the anchor id for a heading, so the slug and the
 * extraction live here rather than being duplicated per component.
 */

export interface HeadingItem {
  level: number
  text: string
  anchorId: string
}

/** Stable, URL-safe id for a heading. Keeps CJK characters, which are common here. */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/<[^>]*>/g, '')
    .replace(/[^\w\u4e00-\u9fff\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/** Strip inline markdown syntax so the outline shows plain text. */
export function extractHeadingText(raw: string): string {
  return raw
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    .replace(/<[^>]*>/g, '')
    .trim()
}

/** Headings found by scanning the raw markdown source (ATX style only). */
export function extractHeadings(content: string): HeadingItem[] {
  if (!content) return []
  const result: HeadingItem[] = []
  for (const line of content.split('\n')) {
    const match = line.match(/^(#{1,6})\s+(.+)/)
    if (!match) continue
    const text = extractHeadingText(match[2].trim())
    result.push({ level: match[1].length, text, anchorId: slugify(text) })
  }
  return result
}

/**
 * Teach a markdown-it instance to put the slug on each rendered heading, so
 * the outline can scroll to it with `querySelector('#' + anchorId)`.
 */
export function installHeadingAnchors(md: any): void {
  md.renderer.rules.heading_open = (tokens: any[], idx: number, options: any, _env: any, self: any) => {
    const inlineToken = tokens[idx + 1]
    if (inlineToken && inlineToken.type === 'inline') {
      tokens[idx].attrSet('id', slugify(extractHeadingText(inlineToken.content)))
    }
    return self.renderToken(tokens, idx, options)
  }
}
