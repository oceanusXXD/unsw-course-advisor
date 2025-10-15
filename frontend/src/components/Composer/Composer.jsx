import React, { useState } from 'react'
import { Send, Square } from 'lucide-react'


export default function Composer({ onSend, loading, onStop }) {
    const [input, setInput] = useState('')
    const handleSubmit = () => {
        if (!input.trim() || loading) return
        onSend(input)
        setInput('')
    }


    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }


    return (
        <div className="border-t border-border-soft bg-bg-surface/50 backdrop-blur-sm">
            <div className="max-w-4xl mx-auto px-6 py-4">
                <div className="relative">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask me anything about UNSW courses..."
                        className="w-full px-5 py-4 pr-14 rounded-xl bg-bg-card border border-border-soft text-text-primary placeholder-text-muted resize-none focus:outline-none focus:border-brand/50 focus:ring-2 focus:ring-brand/20 transition-all"
                        rows={1}
                        style={{ minHeight: '56px', maxHeight: '200px' }}
                    />
                    <button
                        type="button"
                        onClick={loading ? onStop : handleSubmit}
                        disabled={!loading && !input.trim()}
                        className={`absolute right-3 bottom-3 w-10 h-10 rounded-lg flex items-center justify-center transition-all ${loading
                                ? 'bg-red-500 hover:bg-red-600 text-white'
                                : input.trim()
                                    ? 'bg-gradient-to-br from-brand to-brand-dark hover:shadow-lg hover:shadow-brand/30 text-white'
                                    : 'bg-bg-surface text-text-muted cursor-not-allowed'
                            }`}
                    >
                        {loading ? <Square className="w-4 h-4" /> : <Send className="w-4 h-4" />}
                    </button>
                </div>
                <p className="text-xs text-text-muted text-center mt-3">
                    Shift+Enter for newline. Enter to send. Cmd+Ctrl+K to focus composer.
                </p>
            </div>
        </div>
    )
}