import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'

/* ─── Node type → icon SVG path + color ─── */
const NODE_TYPE_META: Record<string, { icon: string; color: string; label: string; bg: string }> = {
  // Triggers (green — matches n8n)
  'n8n-nodes-base.webhook':             { icon: '↯', color: '#ff6d5a', bg: '#ff6d5a18', label: 'Webhook' },
  'n8n-nodes-base.scheduleTrigger':     { icon: '◷', color: '#ff6d5a', bg: '#ff6d5a18', label: 'Schedule' },
  'n8n-nodes-base.manualTrigger':       { icon: '▶', color: '#ff6d5a', bg: '#ff6d5a18', label: 'Manual Trigger' },
  'n8n-nodes-base.emailReadImap':       { icon: '✉', color: '#ff6d5a', bg: '#ff6d5a18', label: 'Email Trigger' },
  'n8n-nodes-base.formTrigger':         { icon: '▤', color: '#ff6d5a', bg: '#ff6d5a18', label: 'Form Trigger' },
  'n8n-nodes-base.errorTrigger':        { icon: '⚠', color: '#ff6d5a', bg: '#ff6d5a18', label: 'Error Trigger' },
  // AI / LangChain
  '@n8n/n8n-nodes-langchain.agent':     { icon: '⚡', color: '#9b59b6', bg: '#9b59b618', label: 'AI Agent' },
  '@n8n/n8n-nodes-langchain.lmChatOpenAi':{ icon: '◆', color: '#10a37f', bg: '#10a37f18', label: 'OpenAI Chat' },
  '@n8n/n8n-nodes-langchain.lmChatAnthropic':{ icon: '◆', color: '#d97706', bg: '#d9770618', label: 'Claude' },
  '@n8n/n8n-nodes-langchain.toolCode': { icon: '⚙', color: '#9b59b6', bg: '#9b59b618', label: 'Code Tool' },
  // Core / Data
  'n8n-nodes-base.httpRequest':         { icon: '⇋', color: '#1a73e8', bg: '#1a73e818', label: 'HTTP Request' },
  'n8n-nodes-base.code':                { icon: '{ }', color: '#e67e22', bg: '#e67e2218', label: 'Code' },
  'n8n-nodes-base.set':                 { icon: '⊞', color: '#e67e22', bg: '#e67e2218', label: 'Edit Fields' },
  'n8n-nodes-base.function':            { icon: 'ƒ', color: '#e67e22', bg: '#e67e2218', label: 'Function' },
  'n8n-nodes-base.splitInBatches':      { icon: '⊟', color: '#607d8b', bg: '#607d8b18', label: 'Loop Over Items' },
  // Conditionals
  'n8n-nodes-base.if':                  { icon: '◇', color: '#e67e22', bg: '#e67e2218', label: 'IF' },
  'n8n-nodes-base.switch':              { icon: '⇶', color: '#e67e22', bg: '#e67e2218', label: 'Switch' },
  'n8n-nodes-base.merge':               { icon: '⊕', color: '#607d8b', bg: '#607d8b18', label: 'Merge' },
  'n8n-nodes-base.filter':              { icon: '⊘', color: '#607d8b', bg: '#607d8b18', label: 'Filter' },
  // Apps
  'n8n-nodes-base.gmail':               { icon: 'M', color: '#ea4335', bg: '#ea433518', label: 'Gmail' },
  'n8n-nodes-base.slack':               { icon: '#', color: '#4a154b', bg: '#4a154b18', label: 'Slack' },
  'n8n-nodes-base.googleSheets':        { icon: '▦', color: '#0f9d58', bg: '#0f9d5818', label: 'Google Sheets' },
  'n8n-nodes-base.notion':              { icon: 'N', color: '#000000', bg: '#ffffff18', label: 'Notion' },
  'n8n-nodes-base.airtable':            { icon: '⬡', color: '#18bfff', bg: '#18bfff18', label: 'Airtable' },
  'n8n-nodes-base.googleDrive':         { icon: '△', color: '#1a73e8', bg: '#1a73e818', label: 'Google Drive' },
  'n8n-nodes-base.postgres':            { icon: '⛁', color: '#336791', bg: '#33679118', label: 'Postgres' },
  'n8n-nodes-base.supabase':            { icon: '⚡', color: '#3ecf8e', bg: '#3ecf8e18', label: 'Supabase' },
  'n8n-nodes-base.respondToWebhook':    { icon: '↩', color: '#1a73e8', bg: '#1a73e818', label: 'Respond Webhook' },
}

const DEFAULT_META = { icon: '⬡', color: '#8e8e93', bg: '#8e8e9318', label: 'Node' }

export interface N8nNodeData {
  name: string
  type: string
  isFirst?: boolean
  isLast?: boolean
}

function N8nNodeComponent({ data }: NodeProps) {
  const nodeData = data as unknown as N8nNodeData
  const isTrigger = nodeData.type?.toLowerCase().includes('trigger') ||
                    nodeData.type === 'n8n-nodes-base.webhook'

  const meta = NODE_TYPE_META[nodeData.type] ?? DEFAULT_META
  const accent = meta.color

  return (
    <>
      {!isTrigger && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            background: '#b0b0b0',
            border: '2px solid #2a2a2a',
            width: 8,
            height: 8,
            borderRadius: '50%',
          }}
        />
      )}

      <div
        style={{
          background: '#2b2b2b',
          borderRadius: 8,
          minWidth: 150,
          maxWidth: 200,
          overflow: 'hidden',
          boxShadow: '0 2px 8px rgba(0,0,0,0.35)',
          border: '1px solid #3a3a3a',
          cursor: 'default',
          transition: 'box-shadow 150ms ease, border-color 150ms ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = `0 4px 16px rgba(0,0,0,0.5), 0 0 0 1px ${accent}55`
          e.currentTarget.style.borderColor = `${accent}66`
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.35)'
          e.currentTarget.style.borderColor = '#3a3a3a'
        }}
      >
        {/* Top accent bar */}
        <div style={{
          height: 3,
          background: accent,
          borderRadius: '8px 8px 0 0',
        }} />

        {/* Content */}
        <div style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Icon circle */}
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: meta.bg,
            border: `1px solid ${accent}33`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.85rem',
            flexShrink: 0,
            color: accent,
            fontWeight: 700,
          }}>
            {meta.icon}
          </div>

          {/* Text */}
          <div style={{ overflow: 'hidden', minWidth: 0 }}>
            <div style={{
              fontSize: '0.6rem',
              fontWeight: 600,
              color: '#888',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              lineHeight: 1,
              marginBottom: 3,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}>
              {meta.label}
            </div>
            <div style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              color: '#e0e0e0',
              lineHeight: 1.25,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}>
              {nodeData.name}
            </div>
          </div>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: '#b0b0b0',
          border: '2px solid #2a2a2a',
          width: 8,
          height: 8,
          borderRadius: '50%',
        }}
      />
    </>
  )
}

export const N8nNode = memo(N8nNodeComponent)
export default N8nNode
