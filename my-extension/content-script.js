// content-script.js - debug 版本：清晰打点并注入 injector.js
(function() {
  try {
    console.log('[EXT CONTENT] content-script executing on', location.href);

    const url = chrome.runtime.getURL('injector.js');

    fetch(url).then(res => {
      if (!res.ok) throw new Error('fetch injector.js failed status=' + res.status);
      return res.text();
    }).then(code => {
      const s = document.createElement('script');
      s.textContent = code + '\n//# sourceURL=injected/injector.js';
      (document.head || document.documentElement).appendChild(s);
      // do not remove immediately in case debugging needed; remove after short delay
      setTimeout(() => s.remove(), 5000);

      // set a page-level flag for detection
      try { window.__ext_injected_flag = true; } catch(e){}

      // notify page and background
      window.postMessage({ source: 'EXT_DEBUG', msg: 'injector injected' }, '*');
      chrome.runtime.sendMessage({ from: 'ext-debug', msg: 'injector injected' }, () => {});
      console.log('[EXT CONTENT] injector.js injected to page context');
    }).catch(err => {
      console.error('[EXT CONTENT] error injecting injector.js', err);
      chrome.runtime.sendMessage({ from: 'ext-debug', msg: 'inject-failed', err: String(err) }, () => {});
    });

    // listen to messages from page/injector
    window.addEventListener('message', (ev) => {
      if (!ev.data) return;
      if (ev.data.source === 'api-runner-page') {
        chrome.runtime.sendMessage({ from: 'api-runner-content', results: ev.data.results, pageUrl: location.href });
      } else if (ev.data.source === 'api-runner-page-ready') {
        chrome.runtime.sendMessage({ from: 'api-runner-content', ready: true, pageUrl: location.href });
        console.log('[EXT CONTENT] received api-runner-page-ready from page');
      } else if (ev.data.source === 'EXT_DEBUG') {
        console.log('[EXT CONTENT] page says:', ev.data.msg);
      }
    });

    // respond to runtime messages (keep original behavior)
    chrome.runtime.onMessage.addListener((msg, sender, sendResp) => {
      if (msg.action === 'runApis' && Array.isArray(msg.urls)) {
        const safeParams = msg.params ? JSON.stringify(msg.params) : 'null';
        const runCode = `window.__apiRunner && window.__apiRunner.run(${JSON.stringify(msg.urls)}, ${safeParams});`;
        const s2 = document.createElement('script');
        s2.textContent = runCode;
        (document.head || document.documentElement).appendChild(s2);
        setTimeout(() => s2.remove(), 2000);
        sendResp({ ok: true });
      }
    });

  } catch (e) {
    console.error('[EXT CONTENT] unexpected error', e);
    try { chrome.runtime.sendMessage({ from: 'ext-debug', msg: 'unexpected-error', err: String(e) }); } catch(e){}
  }
})();
