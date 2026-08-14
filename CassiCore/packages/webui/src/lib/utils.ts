import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * @dep callers: tooltip.tsx (webui/src/components/ui/tooltip/tooltip.tsx), button.tsx (webui/src/components/ui/button.tsx), dialog.tsx (webui/src/components/ui/dialog.tsx), select.tsx (webui/src/components/ui/select.tsx), textarea.tsx (webui/src/components/ui/textarea.tsx) [+52]
 * @dep module: MarkdownRenderer
 * @dep risk: CRITICAL | 57 callers, 0 flows, 1 module
 */

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * @dep callers: SessionItem (webui/src/components/chat/Sidebar/Sessions/SessionItem.tsx), Endpoint (webui/src/components/chat/Sidebar/Sidebar.tsx)
 * @dep module: Sidebar
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export const truncateText = (text: string, limit: number) => {
  if (text) {
    return text.length > limit ? `${text.slice(0, limit)}..` : text
  }
  return ''
}

export const isValidUrl = (url: string): boolean => {
  try {
    const pattern = new RegExp(
      '^https?:\\/\\/' +
        '((([a-zA-Z\\d]([a-zA-Z\\d-]*[a-zA-Z\\d])*)\\.)+[a-zA-Z]{2,}|' +
        'localhost|' +
        '\\d{1,3}(\\.\\d{1,3}){3})' +
        '(\\:\\d+)?' +
        '(\\/[-a-zA-Z\\d%@_.~+&:]*)*' +
        '(\\?[;&a-zA-Z\\d%@_.,~+&:=-]*)?' +
        '(\\#[-a-zA-Z\\d_]*)?$',
      'i'
    )

    return pattern.test(url.trim())
  } catch {
    return false
  }
}

/**
 * @dep callers: useAIChatStreamHandler (webui/src/hooks/useAIStreamHandler.tsx), useSessionLoader (webui/src/hooks/useSessionLoader.tsx)
 * @dep module: Api
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export const getJsonMarkdown = (content: object = {}) => {
  let jsonBlock = ''
  try {
    jsonBlock = `\`\`\`json\n${JSON.stringify(content, null, 2)}\n\`\`\``
  } catch {
    jsonBlock = `\`\`\`\n${String(content)}\n\`\`\``
  }

  return jsonBlock
}
