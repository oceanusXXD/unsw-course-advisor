// src/components/ResultCard.jsx
import React from 'react';

function scoreToPercent(score) {
  // 后端如果返回 cosine in [-1,1]，做归一化；如果是 [0,1] 直接 *100
  if (score <= -1) return 0;
  if (score >= 1) return Math.round(((score + 1) / 2) * 100);
  return Math.round(score * 100);
}

export default function ResultCard({ item }) {
  const score = typeof item.score === 'number' ? item.score : 0;
  const pct = scoreToPercent(score);
  return (
    <div style={{ border: '1px solid #eee', padding: 12, marginBottom: 10, borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ fontWeight: 600 }}>{item.title || item.heading || '匹配片段'}</div>
        <div style={{ minWidth: 120, textAlign: 'right' }}>
          <div style={{ fontSize: 12 }}>相似度: {pct}%</div>
          <div style={{ height: 6, background: '#f1f1f1', borderRadius: 6, marginTop: 4 }}>
            <div style={{ width: `${pct}%`, height: 6, background: '#3b82f6', borderRadius: 6 }} />
          </div>
        </div>
      </div>
      <div style={{ color: '#333', marginBottom: 8 }}>{item.snippet || item.text || ''}</div>
      <div style={{ fontSize: 12, color: '#666' }}>
        来源:
        <a href={item.source_url} target="_blank" rel="noreferrer" style={{ marginLeft: 6 }}>
          {item.source_title || (item.source_url && new URL(item.source_url).hostname) || item.source_url}
        </a>
      </div>
    </div>
  );
}
