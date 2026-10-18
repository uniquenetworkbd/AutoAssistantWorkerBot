(() => {
  "use strict";

  const tg = window.Telegram?.WebApp;
  const form = document.getElementById("target-form");
  const status = document.getElementById("status");
  const environment = document.getElementById("environment");
  const submit = document.getElementById("submit");

  const setStatus = (message, kind = "") => { status.textContent = message; status.className = `status ${kind}`.trim(); };
  const setEnvironment = (message) => { environment.textContent = message; };
  const disable = (message) => { submit.disabled = true; setStatus(message, "error"); };

  if (!tg) { setEnvironment("Telegram session not detected."); disable("Open this page from the Telegram bot Mini App button."); return; }

  tg.ready();
  tg.expand();
  if (tg.MainButton) tg.MainButton.hide();

  if (!tg.initData) { setEnvironment("Telegram authentication data is missing."); disable("Re-open the Mini App from Telegram to continue."); return; }

  setEnvironment("Telegram session detected. Credentials remain server-side.");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const targetUrl = document.getElementById("target-url").value.trim();
    try { const url = new URL(targetUrl); if (!["http:","https:"].includes(url.protocol)) throw new Error(); } catch { setStatus("Enter a valid HTTP or HTTPS target URL.", "error"); return; }

    const payload = {
      version: 1,
      action: "add_target",
      initData: tg.initData,
      target: {
        site_key: document.getElementById("site-key").value.trim(),
        target_url: targetUrl,
        data_selector: document.getElementById("data-selector").value.trim(),
        extract_mode: document.getElementById("extract-mode").value,
        enabled: document.getElementById("enabled").checked
      }
    };

    const encoded = JSON.stringify(payload);
    if (encoded.length > 4096) { setStatus("Payload is too large. Shorten the selector or URL.", "error"); return; }

    submit.disabled = true;
    setStatus("Sending signed Telegram payload…");
    try {
      tg.sendData(encoded);
      setStatus("Submitted. The server will validate Telegram data before updating targets.", "ok");
    } catch (error) {
      console.error("Telegram sendData failed", error);
      setStatus("Telegram could not send the payload. Please try again.", "error");
      submit.disabled = false;
    }
  });
})();
