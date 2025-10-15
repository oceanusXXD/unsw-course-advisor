import React from 'react'
import { User, Sparkles } from 'lucide-react'


export default function MessageBubble({ message, streaming }) {
    const isUser = message.role === 'user'
    return (
        <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${isUser
                    ? 'bg-gradient-to-br from-blue-500 to-purple-600'
                    : 'bg-gradient-to-br from-brand to-brand-dark'
                }`}>
                {isUser ? <User className="w-5 h-5 text-white" /> : <Sparkles className="w-5 h-5 text-white" />}
            </div>
            <div className={`flex-1 ${isUser ? 'flex justify-end' : ''}`}>
                <div className={`inline-block max-w-3xl ${isUser
                        ? 'bg-gradient-to-br from-blue-600 to-purple-600 text-white rounded-2xl rounded-tr-md'
                        : 'bg-bg-card border border-border-soft rounded-2xl rounded-tl-md'
                    } px-5 py-3 shadow-lg`}>
                    <div className={`text-sm leading-relaxed ${isUser ? 'text-white' : 'text-text-primary'}`}>
                        {message.content || (streaming ? <span className="inline-block w-2 h-4 bg-brand animate-caret" /> : '')}
                    </div>
                    {message.time && (
                        <div className={`text-xs mt-2 ${isUser ? 'text-blue-200' : 'text-text-muted'}`}>
                            {message.time}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}