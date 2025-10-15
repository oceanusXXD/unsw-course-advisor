import React from 'react'
import { FileText } from 'lucide-react'


export default function SourcesList({ sources }) {
    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <FileText className="w-4 h-4 text-brand" />
                Sources
            </h3>
            {sources.length === 0 ? (
                <p className="text-xs text-text-muted p-4 text-center rounded-lg bg-bg-card border border-border-soft border-dashed">
                    No sources yet.
                </p>
            ) : (
                <div className="space-y-2">
                    {sources.map((src, i) => (
                        <a
                            key={i}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block p-3 rounded-lg bg-bg-card border border-border-soft hover:border-brand/30 hover:bg-bg-surface transition-all group"
                        >
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand/20 to-brand-dark/20 flex items-center justify-center flex-shrink-0 group-hover:from-brand/30 group-hover:to-brand-dark/30 transition-all">
                                    <FileText className="w-4 h-4 text-brand" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs font-medium text-text-primary group-hover:text-brand transition-colors truncate">
                                        {src.title}
                                    </p>
                                    <p className="text-xs text-text-muted mt-1 line-clamp-2">{src.snippet}</p>
                                </div>
                            </div>
                        </a>
                    ))}
                </div>
            )}
        </div>
    )
}