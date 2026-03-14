/**
 * API Key Bridge for Mintlify Docs
 *
 * Enables automatic API key injection from platform.acedata.cloud
 * into the Mintlify interactive playground's Bearer token field.
 *
 * Flow:
 * 1. User clicks "获取 API Key" button (or the injected "Connect" button)
 * 2. Opens popup to platform.acedata.cloud/auth/bridge
 * 3. User logs in (if needed), bridge page fetches their credential
 * 4. Bridge sends token back via postMessage
 * 5. This script fills the playground's auth input and saves to localStorage
 */
(function () {
  var PLATFORM_URL = 'https://platform.acedata.cloud';
  var STORAGE_KEY = 'acedata-api-key';
  var BRIDGE_PATH = '/auth/bridge';

  // --- Storage ---
  function saveToken(token) {
    try {
      localStorage.setItem(STORAGE_KEY, token);
    } catch (e) {
      // localStorage unavailable
    }
  }

  function loadToken() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function clearToken() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      // ignore
    }
  }

  // --- Playground injection ---
  function findAuthInput() {
    // Mintlify's playground auth input — try common selectors
    // The Bearer token input is typically in the API playground header area
    var selectors = [
      'input[placeholder*="Bearer"]',
      'input[placeholder*="bearer"]',
      'input[placeholder*="Token"]',
      'input[placeholder*="token"]',
      'input[placeholder*="Authorization"]',
      'input[placeholder*="API"]',
      'input[name="Authorization"]',
      'input[aria-label*="Bearer"]',
      'input[aria-label*="Authorization"]',
      'input[aria-label*="Auth"]'
    ];
    for (var i = 0; i < selectors.length; i++) {
      var el = document.querySelector(selectors[i]);
      if (el) return el;
    }

    // Fallback: look for input near text that says "Bearer" or "Authorization"
    var labels = document.querySelectorAll('label, span, p, div');
    for (var j = 0; j < labels.length; j++) {
      var text = labels[j].textContent || '';
      if (/bearer|authorization/i.test(text)) {
        var input = labels[j].closest('div')?.querySelector('input');
        if (input) return input;
      }
    }

    return null;
  }

  function setInputValue(input, value) {
    // React/Vue controlled inputs need native setter + events
    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value'
    )?.set;
    if (nativeInputValueSetter) {
      nativeInputValueSetter.call(input, value);
    } else {
      input.value = value;
    }
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function fillToken(token) {
    var input = findAuthInput();
    if (input) {
      setInputValue(input, token);
      saveToken(token);
      showNotification('API Key 已自动填充', 'success');
      return true;
    }
    // If no input found now, save and retry on next page
    saveToken(token);
    showNotification('API Key 已保存，切换到 API 页面时自动填充', 'info');
    return false;
  }

  // Auto-fill on page navigation (Mintlify is SPA)
  function tryAutoFill() {
    var token = loadToken();
    if (!token) return;
    // Small delay to let playground render
    setTimeout(function () {
      var input = findAuthInput();
      if (input && !input.value) {
        setInputValue(input, token);
      }
    }, 800);
  }

  // --- Notification ---
  function showNotification(message, type) {
    var colors = {
      success: { bg: '#f0f9ff', border: '#6366f1', text: '#4338ca' },
      info: { bg: '#f0f9ff', border: '#6366f1', text: '#4338ca' },
      error: { bg: '#fef2f2', border: '#ef4444', text: '#dc2626' }
    };
    var c = colors[type] || colors.info;

    var el = document.createElement('div');
    el.textContent = message;
    el.style.cssText =
      'position:fixed;top:20px;right:20px;z-index:99999;padding:12px 20px;' +
      'border-radius:8px;font-size:14px;font-weight:500;' +
      'box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:opacity 0.3s;' +
      'background:' + c.bg + ';border:1px solid ' + c.border + ';color:' + c.text;
    document.body.appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0';
      setTimeout(function () {
        el.remove();
      }, 300);
    }, 3000);
  }

  // --- Popup ---
  function openBridgePopup() {
    var w = 500;
    var h = 600;
    var left = (screen.width - w) / 2;
    var top = (screen.height - h) / 2;
    var popup = window.open(
      PLATFORM_URL + BRIDGE_PATH,
      'acedata-bridge',
      'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top + ',menubar=no,toolbar=no,status=no'
    );
    if (!popup) {
      showNotification('弹窗被浏览器拦截，请允许弹窗', 'error');
    }
  }

  // --- Message listener ---
  window.addEventListener('message', function (event) {
    if (event.origin !== PLATFORM_URL) return;
    var data = event.data;
    if (data && data.type === 'acedata-api-key' && data.token) {
      fillToken(data.token);
    }
  });

  // --- Override "获取 API Key" button ---
  function patchNavButton() {
    // Mintlify renders the primary navbar button as an <a> tag
    var links = document.querySelectorAll('a[href="https://platform.acedata.cloud"]');
    links.forEach(function (link) {
      // Only patch the primary CTA button, not the plain "平台" link
      var isButton =
        link.classList.contains('group') ||
        link.closest('button') ||
        /获取|Get|API Key/i.test(link.textContent || '');
      if (isButton) {
        // Check if already has a saved token
        var saved = loadToken();
        if (saved) {
          link.textContent = 'API Key ✓';
          link.title = '点击重新获取 API Key';
        }
        link.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          openBridgePopup();
        });
      }
    });
  }

  // --- Init ---
  function init() {
    // Auto-fill if we have a saved token
    tryAutoFill();
    // Patch the nav button
    patchNavButton();
  }

  // Run on initial load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-run on SPA navigation (Mintlify uses client-side routing)
  var observer = new MutationObserver(function () {
    tryAutoFill();
    patchNavButton();
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
