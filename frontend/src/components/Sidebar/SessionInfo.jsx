import React from 'react'
import { Zap, User, Clock } from 'lucide-react'


export default function SessionInfo({ responseTime, userId }) {
    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Zap className="w-4 h-4 text-brand" />
                Session
            </h3>
            <div className="space-y-2">
                <div className="flex items-center justify-between p-3 rounded-lg bg-bg-card border border-border-soft">
                    <div className="flex items-center gap-2 text-text-secondary text-xs">
                        <User className="w-4 h-4" />
                        <span>User</span>
                    </div>
                    <span className="text-text-primary text-xs font-mono">{userId}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-bg-card border border-border-soft">
                    <div className="flex items-center gap-2 text-text-secondary text-xs">
                        <Clock className="w-4 h-4" />
                        <span>Response time</span>
                    </div>
                    <span className="text-text-primary text-xs font-mono">
                        {responseTime ? `${responseTime.toFixed(2)}s` : '—'}
                    </span>
                </div>
            </div>
        </div>
    )
}