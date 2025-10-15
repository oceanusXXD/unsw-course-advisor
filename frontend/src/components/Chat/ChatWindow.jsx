// src/components/ChatWindow.js
import React from 'react'
import EmptyState from './EmptyState'
import MessageBubble from './MessageBubble'

// Accept `onSuggestionClick` as a prop
export default function ChatWindow({ messages, streaming, onSuggestionClick }) {
    return (
        <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-8">
            <div className="max-w-4xl mx-auto space-y-6">
                {messages.length === 0 ? (
                    // Pass the function down to EmptyState
                    <EmptyState onSuggestionClick={onSuggestionClick} />
                ) : (
                    messages.map((msg, i) => (
                        <MessageBubble key={i} message={msg} streaming={streaming && i === messages.length - 1} />
                    ))
                )}
            </div>
        </div>
    )
}
export {ChatWindow}