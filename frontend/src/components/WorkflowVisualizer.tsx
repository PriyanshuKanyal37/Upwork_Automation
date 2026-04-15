import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  type Node,
  type Edge,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { N8nNode } from './N8nNode'
import type { N8nNodeData } from './N8nNode'

/* ─────────────────────────────────────────────
   Types for the n8n workflow JSON structure
───────────────────────────────────────────── */
interface N8nWorkflowNode {
  id: string
  name: string
  type: string
  position: [number, number]
  parameters?: Record<string, unknown>
}

interface N8nWorkflow {
  name?: string
  nodes?: N8nWorkflowNode[]
  connections?: Record<string, {
    main?: Array<Array<{ node: string; type: string; index: number }>>
  }>
}

/* ─────────────────────────────────────────────
   Parse n8n workflow JSON → RF nodes + edges
───────────────────────────────────────────── */
const HORIZONTAL_SPACING = 260

function parseWorkflow(wf: N8nWorkflow): { nodes: Node[]; edges: Edge[] } {
  const rawNodes: N8nWorkflowNode[] = wf.nodes ?? []
  const connections = wf.connections ?? {}

  const nodes: Node[] = rawNodes.map((n, idx) => {
    const hasPos = n.position && (n.position[0] !== 0 || n.position[1] !== 0)
    const x = hasPos ? n.position[0] : idx * HORIZONTAL_SPACING
    const y = hasPos ? n.position[1] : 100

    return {
      id: n.id || n.name,
      type: 'n8nNode',
      position: { x, y },
      data: {
        name: n.name,
        type: n.type,
      } satisfies N8nNodeData,
    }
  })

  const nameToId: Record<string, string> = {}
  rawNodes.forEach(n => { nameToId[n.name] = n.id || n.name })

  const edges: Edge[] = []
  let edgeCounter = 0

  Object.entries(connections).forEach(([sourceName, conn]) => {
    const sourceId = nameToId[sourceName]
    if (!sourceId) return

    const mainOutputs = conn.main ?? []
    mainOutputs.forEach((outputGroup, outputIndex) => {
      ;(outputGroup ?? []).forEach(target => {
        const targetId = nameToId[target.node]
        if (!targetId) return

        const branchLabel = mainOutputs.length > 1
          ? outputIndex === 0 ? 'true' : outputIndex === 1 ? 'false' : `out ${outputIndex}`
          : undefined

        edges.push({
          id: `e-${edgeCounter++}`,
          source: sourceId,
          target: targetId,
          sourceHandle: null,
          type: 'smoothstep',
          animated: false,
          label: branchLabel,
          style: {
            stroke: '#6b6b6b',
            strokeWidth: 1.5,
          },
          labelStyle: {
            fill: '#999',
            fontSize: 9,
            fontWeight: 600,
          },
          labelBgStyle: {
            fill: '#1e1e1e',
            opacity: 0.9,
          },
          labelBgPadding: [4, 4] as [number, number],
          labelBgBorderRadius: 4,
        })
      })
    })
  })

  return { nodes, edges }
}

/* ─────────────────────────────────────────────
   n8n logo SVG
───────────────────────────────────────────── */
function N8nLogo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <rect width="40" height="40" rx="8" fill="#ea4b71" />
      <text x="20" y="28" textAnchor="middle" fill="white" fontSize="20" fontWeight="700" fontFamily="Inter, sans-serif">n8n</text>
    </svg>
  )
}

/* ─────────────────────────────────────────────
   Single flow canvas (used both inline and fullscreen)
───────────────────────────────────────────── */
const nodeTypes = { n8nNode: N8nNode }

function FlowCanvas({ workflow, height }: { workflow: N8nWorkflow; height: number }) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => parseWorkflow(workflow),
    [workflow]
  )

  const [nodes, , onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)

  const onConnect = useCallback(
    (params: Connection) => setEdges(prev => addEdge(params, prev)),
    [setEdges]
  )

  return (
    <div style={{ width: '100%', height, background: '#1a1a1a', overflow: 'hidden' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.2}
        maxZoom={3}
        deleteKeyCode={null}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        proOptions={{ hideAttribution: true }}
        style={{ background: 'transparent' }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="rgba(255,255,255,0.05)"
        />
        <Controls
          showInteractive={false}
          style={{
            background: '#2b2b2b',
            border: '1px solid #3a3a3a',
            borderRadius: 8,
            boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
          }}
        />
        <MiniMap
          nodeColor={(n) => {
            const type = (n.data as unknown as N8nNodeData).type ?? ''
            if (type.includes('Trigger') || type.includes('trigger') || type.includes('webhook')) return '#ff6d5a'
            if (type.includes('langchain')) return '#9b59b6'
            if (type.includes('code') || type.includes('set') || type.includes('function')) return '#e67e22'
            if (type.includes('if') || type.includes('switch')) return '#e67e22'
            if (type.includes('slack')) return '#4a154b'
            if (type.includes('airtable')) return '#18bfff'
            if (type.includes('httpRequest')) return '#1a73e8'
            return '#6b6b6b'
          }}
          maskColor="rgba(20,20,20,0.85)"
          style={{
            background: '#2b2b2b',
            border: '1px solid #3a3a3a',
            borderRadius: 8,
          }}
        />
      </ReactFlow>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Fullscreen overlay modal
───────────────────────────────────────────── */
function FullscreenModal({
  workflow,
  onClose,
}: {
  workflow: N8nWorkflow
  onClose: () => void
}) {
  const nodeCount = workflow.nodes?.length ?? 0

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: '#111',
        display: 'flex',
        flexDirection: 'column',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      {/* Top bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 20px',
        background: '#1a1a1a',
        borderBottom: '1px solid #2a2a2a',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <N8nLogo size={24} />
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e0e0e0' }}>
            {workflow.name || 'Workflow'}
          </span>
          <span style={{
            fontSize: '0.7rem', fontWeight: 600, color: '#999',
            background: '#2b2b2b', padding: '3px 10px', borderRadius: 100,
            border: '1px solid #3a3a3a',
          }}>
            {nodeCount} node{nodeCount !== 1 ? 's' : ''}
          </span>
        </div>

        <button
          type="button"
          onClick={onClose}
          style={{
            background: '#2b2b2b',
            border: '1px solid #3a3a3a',
            borderRadius: 8,
            padding: '6px 16px',
            color: '#ccc',
            fontSize: '0.8rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            transition: 'all 120ms',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#3a3a3a'
            e.currentTarget.style.borderColor = '#555'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#2b2b2b'
            e.currentTarget.style.borderColor = '#3a3a3a'
          }}
        >
          <span style={{ fontSize: '1rem' }}>×</span> Close
        </button>
      </div>

      {/* Canvas takes remaining space */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <FlowCanvas workflow={workflow} height={window.innerHeight - 52} />
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Main: WorkflowVisualizer
───────────────────────────────────────────── */
interface WorkflowVisualizerProps {
  content: string
}

export function WorkflowVisualizer({ content }: WorkflowVisualizerProps) {
  const [activeTab, setActiveTab] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const workflows: N8nWorkflow[] = useMemo(() => {
    try {
      const parsed = JSON.parse(content)
      if (Array.isArray(parsed)) return parsed as N8nWorkflow[]
      return [parsed as N8nWorkflow]
    } catch {
      return []
    }
  }, [content])

  if (workflows.length === 0) {
    return (
      <div style={{
        padding: '32px 24px', textAlign: 'center',
        color: '#888', fontSize: '0.875rem',
      }}>
        Could not parse workflow JSON.
      </div>
    )
  }

  const activeWf = workflows[activeTab] ?? workflows[0]
  const nodeCount = activeWf.nodes?.length ?? 0

  return (
    <div>
      {/* Tab row — only show when multiple workflows */}
      {workflows.length > 1 && (
        <div style={{
          display: 'flex', gap: 6, padding: '10px 20px',
          borderBottom: '1px solid #2a2a2a', flexWrap: 'wrap',
        }}>
          {workflows.map((wf, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setActiveTab(i)}
              style={{
                padding: '4px 14px', borderRadius: 100, fontSize: '0.78rem', fontWeight: 600,
                border: '1px solid',
                cursor: 'pointer',
                transition: 'all 140ms',
                borderColor: i === activeTab ? 'var(--primary)' : '#3a3a3a',
                background: i === activeTab ? 'var(--primary-glow)' : 'transparent',
                color: i === activeTab ? 'var(--primary)' : '#888',
              }}
            >
              {wf.name ?? `Workflow ${i + 1}`}
            </button>
          ))}
        </div>
      )}

      {/* Header with metadata and expand button */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 20px', borderBottom: '1px solid #2a2a2a',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <N8nLogo />
          {activeWf.name && (
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#e0e0e0' }}>
              {activeWf.name}
            </span>
          )}
          <span style={{
            fontSize: '0.68rem', fontWeight: 600, color: '#999',
            background: '#2b2b2b', padding: '2px 8px', borderRadius: 100,
            border: '1px solid #3a3a3a',
          }}>
            {nodeCount} node{nodeCount !== 1 ? 's' : ''}
          </span>
          <span style={{ fontSize: '0.68rem', color: '#666' }}>
            Pan & scroll to zoom
          </span>
        </div>

        <button
          type="button"
          onClick={() => setIsFullscreen(true)}
          style={{
            background: '#2b2b2b',
            border: '1px solid #3a3a3a',
            borderRadius: 8,
            padding: '5px 14px',
            color: '#ccc',
            fontSize: '0.75rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            transition: 'all 120ms',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#3a3a3a'
            e.currentTarget.style.borderColor = '#555'
            e.currentTarget.style.color = '#fff'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#2b2b2b'
            e.currentTarget.style.borderColor = '#3a3a3a'
            e.currentTarget.style.color = '#ccc'
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
          </svg>
          Expand
        </button>
      </div>

      {/* Inline canvas */}
      <div style={{ padding: '12px 16px' }}>
        <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid #2a2a2a' }}>
          <FlowCanvas key={activeTab} workflow={activeWf} height={420} />
        </div>
      </div>

      {/* Fullscreen overlay */}
      {isFullscreen && (
        <FullscreenModal
          workflow={activeWf}
          onClose={() => setIsFullscreen(false)}
        />
      )}
    </div>
  )
}

export default WorkflowVisualizer
