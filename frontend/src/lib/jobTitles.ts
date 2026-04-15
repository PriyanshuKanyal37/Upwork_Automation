import type { JobRecord } from './api'

function firstMeaningfulLine(source: string | null | undefined) {
  if (!source) return null
  const lines = source
    .split('\n')
    .map((line) => line.replace(/^#+\s*/, '').trim())
    .filter(Boolean)
  return lines[0] ?? null
}


export function deriveJobTitle(job: JobRecord) {
  const markdownLine = firstMeaningfulLine(
    typeof job.job_markdown === 'string' ? job.job_markdown : null,
  )
  if (markdownLine) return markdownLine.slice(0, 72)

  const noteLine = firstMeaningfulLine(
    typeof job.notes_markdown === 'string' ? job.notes_markdown : null,
  )
  if (noteLine) return noteLine.slice(0, 72)

  return 'New Chat'
}
