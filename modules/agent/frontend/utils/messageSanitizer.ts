import type { DesktopEventWindow, RefItem, SanitizedMessage } from '../types'

function normalizeRefTitle(title: string): string {
  return title.replace(/^\d+[.)、]\s*/, '').trim()
}

export function uniqueRefs(refs: RefItem[]): RefItem[] {
  const seen = new Set<string>()
  const out: RefItem[] = []
  for (const ref of refs) {
    const key = ref.url || `${ref.type}:${ref.title || ref.source || ''}`
    if (!key || seen.has(key)) continue
    seen.add(key)
    out.push(ref)
  }
  return out
}

export function sanitizeAssistantMessage(text: string): SanitizedMessage {
  let content = cleanXmlContent(text)
  content = content.replace(/<p>\s*<strong>\s*最佳路径总结[:：]\s*<\/strong>[\s\S]*?<\/p>/gi, '')
  content = content.replace(/(?:^|\n)\s*(?:\*\*)?最佳路径总结[:：](?:\*\*)?[\s\S]*?(?=\n\s*📎\s*来源[:：]|\n\s*#{1,6}\s|\n\s*[-*]\s|$)/gi, '\n')
  const references: RefItem[] = []
  const htmlSourceMatch = content.match(/<p>\s*📎\s*来源[:：]?\s*<\/p>\s*<ul>([\s\S]*?)<\/ul>/i)
  const markdownSourceMatch = content.match(/(?:^|\n)\s*📎\s*来源[:：]?\s*\n?([\s\S]*)$/)
  const sourceBlock = htmlSourceMatch?.[1] || markdownSourceMatch?.[1] || ''
  if (sourceBlock) {
    const linkRe = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|<a\s+[^>]*href=["'](https?:\/\/[^"']+)["'][^>]*>(.*?)<\/a>/gi
    let match: RegExpExecArray | null
    while ((match = linkRe.exec(sourceBlock)) !== null) {
      const title = normalizeRefTitle((match[1] || match[4] || match[2] || match[3] || '').replace(/<[^>]+>/g, ''))
      const url = match[2] || match[3]
      if (title || url) references.push({ type: 'web', title: title || url, source: title || url, excerpt: '', url })
    }
    if (references.length) {
      if (htmlSourceMatch?.[0]) {
        content = content.replace(htmlSourceMatch[0], '').trim()
      } else if (markdownSourceMatch) {
        content = content.slice(0, markdownSourceMatch.index).trim()
      }
    }
  }
  return { content: content.trim(), references: uniqueRefs(references) }
}

function cleanXmlContent(text: string): string {
  const normalized = text
    .replace(/<｜｜DSML｜｜/g, '<')
    .replace(/<\/｜｜DSML｜｜/g, '</')
  return normalized
    .replace(/<\w*:?tool_calls?[\s\S]*?<\/\w*:?tool_calls?\s*>/gi, '')
    .replace(/<\w*:?invoke[\s\S]*?<\/\w*:?invoke\s*>/gi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function triggerDesktopRefresh(): void {
  try {
    const eventWindow = window as DesktopEventWindow
    if (eventWindow.__DESKTOP_EVENT_BUS__) {
      eventWindow.__DESKTOP_EVENT_BUS__.emit('refresh:file-list', {})
    }
    window.dispatchEvent(new CustomEvent('desktop:refresh-files'))
  } catch { /* non-critical desktop notification */ }
}
