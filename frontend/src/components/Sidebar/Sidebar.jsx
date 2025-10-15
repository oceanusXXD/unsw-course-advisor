import React from 'react'
import SessionInfo from './SessionInfo'
import SourcesList from './SourcesList'

export default function Sidebar({ sources, responseTime, userId }) {
    return (
        <aside className="w-full md:w-[320px] xl:w-[360px] border-l border-border-soft bg-bg-surface/50 backdrop-blur-sm">
            {/* 这个 div 负责粘性定位和滚动 */}
            <div className="sticky top-[57px] max-h-[calc(100vh-57px)] overflow-auto p-4 space-y-4">
                
                {/* 会话信息组件 */}
                <SessionInfo responseTime={responseTime} userId={userId} />

                {/* 来源列表组件 */}
                <SourcesList sources={sources} />

            </div>
        </aside>
    )
}