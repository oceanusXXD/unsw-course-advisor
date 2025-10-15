// src/components/SearchPanel.jsx
import React, { useState, useEffect } from 'react';
import useDebounce from '../../hooks/useDebounce';
import { apiGet, apiPost } from '../../services/apiClient';
import ResultCard from '../ResultCard/ResultCard';

export default function SearchPanel() {
  const [q, setQ] = useState('');
  const debouncedQ = useDebounce(q, 400);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!debouncedQ || debouncedQ.trim().length < 2) {
      setResults([]);
      setErr(null);
      return;
    }
    let mounted = true;
    setLoading(true);
    setErr(null);

    // 假设后端 API: GET /search?q=xxx  返回 { results: [{id, source_url, snippet, score}, ...] }
    apiGet(`/search?q=${encodeURIComponent(debouncedQ)}`)
      .then(data => {
        if (!mounted) return;
        setResults(data.results || []);
      })
      .catch(e => {
        console.error('search error', e);
        if (!mounted) return;
        setErr(e.message || '搜索出错');
      })
      .finally(() => mounted && setLoading(false));

    return () => { mounted = false; };
  }, [debouncedQ]);

  return (
    <div style={{ padding: 16, maxWidth: 900, margin: '0 auto' }}>
      <h2>课程问答 / 搜索</h2>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="输入课程名 / 代码 / 问题（例如：COMP1511 推荐）"
        style={{ width: '100%', padding: 10, fontSize: 16, boxSizing: 'border-box' }}
      />
      {loading && <div style={{ marginTop: 12 }}>搜索中…</div>}
      {err && <div style={{ color: 'red', marginTop: 12 }}>{err}</div>}
      <div style={{ marginTop: 12 }}>
        {results.length === 0 && !loading && debouncedQ && <div>没有命中结果（可尝试更通用的关键词）</div>}
        {results.map(r => <ResultCard key={r.id || r.doc_id || r.source_url} item={r} />)}
      </div>
    </div>
  );
}
