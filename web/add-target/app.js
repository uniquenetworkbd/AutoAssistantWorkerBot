(() => {
  "use strict";

  const tg = window.Telegram?.WebApp;
  const form = document.getElementById("target-form");
  const status = document.getElementById("status");
  const submit = document.getElementById("submit");

  function setStatus(message, kind = "") {
    status.textContent = message;
    status.className = `status ${kind}`.trim();
  }

  if (!tg) {
    setStatus("Open this page from the Telegram bot /add_target button.", "error");
    submit.disabled = true;
    return;
  }

  tg.ready();
  tg.expand();
  if (tg.MainButton) tg.MainButton.hide();

  if (!tg.initData) {
    setStatus("Telegram authorization data is unavailable. Re-open the Mini App from Telegram.", "error");
    submit.disabled = true;
    return;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const payload = {
      version: 1,
      action: "add_target",
      initData: tg.initData,
      target: {
        site_key: document.getElementById("site-key").value.trim(),
        target_url: document.getElementById("target-url").value.trim(),
        data_selector: document.getElementById("data-selector").value.trim(),
        extract_mode: document.getElementById("extract-mode").value,
        enabled: document.getElementById("enabled").checked
      }
    };

    const encoded = JSON.stringify(payload);
    if (encoded.length > 4096) {
      setStatus("Payload is too large. Shorten the selector or URL.", "error");
      return;
    }

    submit.disabled = true;
    setStatus("Sending to Telegram…");
    try {
      // Telegram supplies initData with its signed authentication data.
      // The client never knows or receives a bot credential.
      tg.sendData(encoded);
      setStatus("Submitted. The bot will validate the signed data and update the target list.", "ok");
    } catch (error) {
      console.error("Telegram sendData failed", error);
      setStatus("Telegram could not send the payload. Please try again.", "error");
      submit.disabled = false;
    }
  });
})();
