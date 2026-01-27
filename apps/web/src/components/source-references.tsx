import { FileText, ExternalLink, ChevronDown, ChevronUp, BookOpen } from "lucide-react"
import { useState } from "react"
import type { SourceInfo } from "@/lib/api"

interface SourceReferencesProps {
  sources: SourceInfo[]
}

export default function SourceReferences({ sources }: SourceReferencesProps) {
  if (!sources || sources.length === 0) {
    return null
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <BookOpen size={16} />
        <span>Nguồn tham khảo ({sources.length})</span>
      </div>
      <div className="space-y-2">
        {sources.map((source, index) => (
          <SourceCard key={`${source.doc_id}-${index}`} source={source} index={index} />
        ))}
      </div>
    </div>
  )
}

interface SourceCardProps {
  source: SourceInfo
  index: number
}

function SourceCard({ source, index }: SourceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const isRegulation = source.doc_type === "regulation"
  const hasNodes = source.nodes && source.nodes.length > 0

  return (
    <div className="border border-border rounded-lg bg-card/50 overflow-hidden hover:border-primary/50 transition-colors">
      {/* Header */}
      <div className="p-3 space-y-2">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div
            className={`flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center ${
              isRegulation ? "bg-blue-500/10 text-blue-600" : "bg-green-500/10 text-green-600"
            }`}
          >
            {isRegulation ? <FileText size={16} /> : <ExternalLink size={16} />}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-1">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-medium text-foreground truncate">{source.doc_title}</h4>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      isRegulation
                        ? "bg-blue-500/10 text-blue-700 dark:text-blue-400"
                        : "bg-green-500/10 text-green-700 dark:text-green-400"
                    }`}
                  >
                    {isRegulation ? "Quy định" : "Chương trình"}
                  </span>
                  <span className="text-xs text-muted-foreground">{source.year}</span>
                </div>
              </div>

              {/* Action Button */}
              <div className="flex-shrink-0">
                {isRegulation && source.pdf_url ? (
                  <a
                    href={source.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 rounded-md transition-colors"
                  >
                    <FileText size={14} />
                    <span>Xem PDF</span>
                  </a>
                ) : !isRegulation && source.source_url ? (
                  <a
                    href={source.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-green-700 dark:text-green-400 bg-green-500/10 hover:bg-green-500/20 rounded-md transition-colors"
                  >
                    <ExternalLink size={14} />
                    <span>Xem trên Web</span>
                  </a>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        {/* Node Summary */}
        {hasNodes && (
          <div className="pl-11">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>
                {isExpanded ? "Ẩn" : "Hiển thị"} {source.nodes.length} đoạn trích dẫn
              </span>
            </button>
          </div>
        )}
      </div>

      {/* Expanded Nodes */}
      {isExpanded && hasNodes && (
        <div className="border-t border-border bg-muted/30">
          <div className="p-3 space-y-2">
            {source.nodes.map((node, nodeIndex) => (
              <div
                key={`${node.node_id}-${nodeIndex}`}
                className="p-2.5 bg-background rounded-md border border-border/50 space-y-1.5"
              >
                {/* Node Title */}
                <div className="flex items-start gap-2">
                  <span className="flex-shrink-0 text-xs font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                    {node.node_id}
                  </span>
                  <p className="text-xs font-medium text-foreground flex-1">{node.title}</p>
                </div>

                {/* Node Text (Truncated) */}
                <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3 pl-0">
                  {node.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
