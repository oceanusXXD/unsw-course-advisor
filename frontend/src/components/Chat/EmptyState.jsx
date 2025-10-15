// src/components/EmptyState.js

import React from 'react'
import { Sparkles, MessageSquare, Book, Zap } from 'lucide-react'

// Accept a new prop `onSuggestionClick`
export default function EmptyState({ onSuggestionClick }) {
    const suggestions = [
        { icon: Sparkles, text: "What are the prerequisites for COMP2521?", color: "from-purple-500 to-pink-500" },
        { icon: Book, text: "Tell me about Computer Science courses", color: "from-blue-500 to-cyan-500" },
        { icon: Zap, text: "What's the difference between COMP and SENG?", color: "from-green-500 to-emerald-500" }
    ]

    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
            {/* ... (rest of your UI code is the same) ... */}
            <div className="relative mb-8">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand via-brand-soft to-brand-dark flex items-center justify-center shadow-2xl shadow-brand/30 animate-pulse">
                    <MessageSquare className="w-10 h-10 text-white" />
                </div>
                <div className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 animate-bounce" />
            </div>
            <h2 className="text-3xl font-bold text-text-primary mb-3 bg-gradient-to-r from-text-primary via-brand to-brand-dark bg-clip-text text-transparent">
                Start by asking a question
            </h2>
            <p className="text-text-secondary mb-8 max-w-md">
                Ask me anything about UNSW courses, prerequisites, course content, or career paths.
            </p>

            <div className="grid grid-cols-1 gap-3 w-full max-w-2xl">
                {suggestions.map((item, i) => (
                    <button
                        key={i}
                        // Add the onClick handler here
                        onClick={() => onSuggestionClick(item.text)}
                        className="group flex items-center gap-4 p-4 rounded-xl bg-bg-card border border-border-soft hover:border-brand/30 hover:bg-bg-surface transition-all text-left"
                    >
                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${item.color} flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform`}>
                            <item.icon className="w-5 h-5 text-white" />
                        </div>
                        <span className="text-text-primary text-sm group-hover:text-brand transition-colors">{item.text}</span>
                    </button>
                ))}
            </div>

            <p className="text-xs text-text-muted mt-8">
                Press <kbd className="px-2 py-1 rounded bg-bg-card border border-border-soft">⌘K</kbd> for command palette
            </p>
        </div>
    )
}