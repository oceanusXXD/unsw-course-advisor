// injector.js - debug 版本（页面上下文）
(function() {
  if (window.__apiRunner) {
    console.log('[INJECTOR] __apiRunner already present');
    window.__apiRunner_ready = true;
    return;
  }

  window.__apiRunner = {
    run: async function(urls, params) {
      const results = [];
      for (const url of urls) {
        try {
          const resp = await fetch(url, { credentials: 'include', method: 'GET' });
          const text = await resp.text();
          results.push({ url, status: resp.status, len: text ? text.length : 0, snippet: text ? text.slice(0,300) : '' });
        } catch (e) {
          results.push({ url, status: 'error', err: String(e) });
        }
      }
      window.postMessage({ source: 'api-runner-page', results }, '*');
      return results;
    }
  };

  // 标记与可观测输出
  try {
    window.__apiRunner_ready = true;
    console.log('打开成功');   // 页面 console 可见
    // 也发一个可被 content-script 捕获的 postMessage
    window.postMessage({ source: 'api-runner-page-ready', msg: 'injector ready' }, '*');
  } catch (e) {
    console.error('[INJECTOR] error logging ready', e);
  }

  // 保持原有 message handler
  window.addEventListener('message', async (ev) => {
    try {
      if (!ev.data || typeof ev.data !== 'object') return;
      if (ev.data.source === 'server-trigger' && ev.data.action === 'runApis') {
        const results = await window.__apiRunner.run(ev.data.urls || [], ev.data.params || null);
        try { ev.source.postMessage({ source: 'server-trigger-reply', ok: true, results }, ev.origin || '*'); } catch (e) {}
      }
    } catch (e) {
      console.error('[INJECTOR] message handler error', e);
    }
  });
})();
