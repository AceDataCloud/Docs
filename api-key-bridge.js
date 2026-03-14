/**
 * API Key Bridge for Mintlify Docs
 *
 * Flow:
 * 1. User clicks nav button -> opens popup to platform auth bridge
 * 2. User authenticates, bridge sends token back via postMessage
 * 3. Token saved to localStorage, copied to clipboard for easy paste
 * 4. On API pages, tries to auto-fill the playground Bearer token input
 */
(function () {
  var PLATFORM_URL = "https://platform.acedata.cloud";
  var STORAGE_KEY = "acedata-api-key";
  var BRIDGE_PATH = "/auth/bridge";

  function saveToken(t) {
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch (e) {
      /* noop */
    }
  }
  function loadToken() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function notify(msg, isError) {
    var el = document.createElement("div");
    el.textContent = msg;
    el.style.cssText =
      "position:fixed;top:20px;right:20px;z-index:99999;padding:12px 20px;" +
      "border-radius:8px;font-size:14px;font-weight:500;" +
      "box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:opacity 0.3s;" +
      "background:" +
      (isError ? "#fef2f2" : "#f0f9ff") +
      ";" +
      "border:1px solid " +
      (isError ? "#ef4444" : "#6366f1") +
      ";" +
      "color:" +
      (isError ? "#dc2626" : "#4338ca");
    document.body.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () {
        el.remove();
      }, 300);
    }, 3000);
  }

  function tryFillPlayground(token) {
    var selectors = [
      'input[placeholder*="Bearer"]',
      'input[placeholder*="bearer"]',
      'input[placeholder*="<token>"]',
      'input[placeholder*="Token"]',
      'input[placeholder*="Authorization"]',
      'input[name="Authorization"]',
      'input[aria-label*="Bearer"]',
      'input[aria-label*="Authorization"]',
    ];
    for (var i = 0; i < selectors.length; i++) {
      var input = document.querySelector(selectors[i]);
      if (input) {
        var setter = Object.getOwnPropertyDescriptor(
          HTMLInputElement.prototype,
          "value",
        );
        if (setter && setter.set) {
          setter.set.call(input, token);
        } else {
          input.value = token;
        }
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
    return false;
  }

  function openBridge() {
    var w = 500,
      h = 600;
    var popup = window.open(
      PLATFORM_URL + BRIDGE_PATH,
      "acedata-bridge",
      "width=" +
        w +
        ",height=" +
        h +
        ",left=" +
        (screen.width - w) / 2 +
        ",top=" +
        (screen.height - h) / 2 +
        ",menubar=no,toolbar=no,status=no",
    );
    if (!popup)
      notify(
        "\u5f39\u7a97\u88ab\u62e6\u622a\uff0c\u8bf7\u5141\u8bb8\u5f39\u7a97",
        true,
      );
  }

  window.addEventListener("message", function (e) {
    if (e.origin !== PLATFORM_URL) return;
    var d = e.data;
    if (d && d.type === "acedata-api-key" && d.token) {
      saveToken(d.token);
      var filled = tryFillPlayground(d.token);
      if (filled) {
        notify("API Key \u5df2\u81ea\u52a8\u586b\u5145");
      } else {
        navigator.clipboard
          .writeText(d.token)
          .then(function () {
            notify(
              "API Key \u5df2\u4fdd\u5b58\u5e76\u590d\u5236\u5230\u526a\u8d34\u677f\uff0c\u53ef\u76f4\u63a5\u7c98\u8d34",
            );
          })
          .catch(function () {
            notify(
              "API Key \u5df2\u4fdd\u5b58\uff0c\u8bf7\u5230 Playground \u624b\u52a8\u8f93\u5165",
            );
          });
      }
      patchButtons();
    }
  });

  function patchButtons() {
    var links = document.querySelectorAll(
      'a[href="https://platform.acedata.cloud"]',
    );
    var saved = loadToken();
    links.forEach(function (link) {
      if (link._bridgePatched) return;
      var text = (link.textContent || "").trim();
      if (/\u83b7\u53d6|Get|API.?Key/i.test(text)) {
        link._bridgePatched = true;
        if (saved) {
          link.textContent = "API Key \u2713";
          link.title = "\u70b9\u51fb\u91cd\u65b0\u83b7\u53d6 API Key";
        }
        link.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          openBridge();
        });
      }
    });
  }

  function autoFill() {
    var token = loadToken();
    if (!token) return;
    setTimeout(function () {
      tryFillPlayground(token);
    }, 1500);
  }

  function init() {
    patchButtons();
    autoFill();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // SPA navigation: intercept history API (safe, no DOM watching)
  var lastHref = location.href;
  function onNav() {
    if (location.href === lastHref) return;
    lastHref = location.href;
    setTimeout(init, 500);
  }
  var _push = history.pushState;
  history.pushState = function () {
    _push.apply(this, arguments);
    onNav();
  };
  var _replace = history.replaceState;
  history.replaceState = function () {
    _replace.apply(this, arguments);
    onNav();
  };
  window.addEventListener("popstate", onNav);
})();
