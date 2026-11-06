import ReactMarkdown from 'react-markdown'

interface MarkdownPreviewProps {
  markdown: string
}

// react-markdown without rehype-raw never renders embedded HTML, so this is
// safe to use directly on untrusted job-description content.
export function MarkdownPreview({ markdown }: MarkdownPreviewProps) {
  return (
    <div className="markdown-body text-sm text-ink-600">
      <ReactMarkdown>{markdown}</ReactMarkdown>
    </div>
  )
}
