import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { cn } from "@/lib/cn";
import { User, Bot } from 'lucide-react'

export default function MessageItem({ message, isStreaming }) {
    const isUser = message.role === 'user'
    return (
        <div className={cn('flex gap-3 w-full', isUser ? 'justify-end' : 'justify-start')}>
            {!isUser ? (
                <div className="w-8 h-8 rounded-md bg-gradient-to-b from-brand to-brand-dark flex items-center justify-center text-white flex-shrink-0">
                    <Bot size={16} />
                </div>
            ) : null}
            <div
                className={cn(
                    'max-w-[92%] md:max-w-[80%] rounded-xl px-4 py-3 border',
                    isUser
                        ? 'bg-brand/10 border-brand/20'
                        : 'bg-bg-card/70 border-border-soft'
                )}
            >
                <div className="text-xs text-text-muted mb-1">
                    {isUser ? 'You' : 'Assistant'} · {message.time}
                </div>
                {isUser ? (
                    <div className="whitespace-pre-wrap leading-7">{message.content}</div>
                ) : (
                    <div className="markdown prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                            {message.content || ''}
                        </ReactMarkdown>
                        {isStreaming && !message.content?.endsWith('[stopped]') ? (
                            <span className="inline-block w-2 h-4 bg-text-primary/60 ml-0.5 align-bottom animate-caret" />
                        ) : null}
                    </div>
                )}
            </div>

            {isUser ? (
                <div className="w-8 h-8 rounded-md bg-bg-surface border border-border-soft flex items-center justify-center text-text-secondary flex-shrink-0">
                    <User size={16} />
                </div>
            ) : null}
        </div>
    )
}