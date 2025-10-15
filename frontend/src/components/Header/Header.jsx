// File: ./components/Header/Header.jsx
import React from 'react'
import { Book, User } from 'lucide-react'


export default function Header({ userId, setUserId, onNewChat, onToggleSources, sourcesOpen, loading }) {
    return (
        <header className="border-b border-border-soft bg-bg-surface/50 backdrop-blur-sm sticky top-0 z-10">
            <div className="px-6 py-4 flex items-center justify-between max-w-7xl mx-auto">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center shadow-lg shadow-brand/20">
                        <Book className="w-6 h-6 text-white" />
                    </div>
                    <div>
                        <h1 className="text-lg font-semibold text-text-primary">UNSW Course Advisor</h1>
                        <p className="text-xs text-text-muted">LangGraph v3.3 · React</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-card border border-border-soft">
                        <User className="w-4 h-4 text-text-muted" />
                        <input
                            type="text"
                            value={userId}
                            onChange={(e) => setUserId(e.target.value)}
                            className="bg-transparent text-sm text-text-primary border-none outline-none w-40"
                            placeholder="User ID"
                        />
                    </div>
                    <button
                        onClick={onNewChat}
                        disabled={loading}
                        className="px-4 py-2 rounded-lg bg-bg-card hover:bg-bg-base border border-border-soft text-text-primary text-sm font-medium transition-all hover:border-brand/30 disabled:opacity-50"
                    >
                        New chat
                    </button>
                    <button
                        onClick={onToggleSources}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${sourcesOpen
                                ? 'bg-brand/10 text-brand border border-brand/20'
                                : 'bg-bg-card text-text-primary border border-border-soft hover:border-brand/30'
                            }`}
                    >
                        {sourcesOpen ? 'Hide' : 'Show'} sources
                    </button>
                </div>
            </div>
        </header>
    )
}
export { Header }