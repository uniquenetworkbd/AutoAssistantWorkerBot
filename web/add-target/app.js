(() => {
  const tg = window.Telegram?.WebApp;
  const form = document.getElementById('target-form');
  const status = document.getElementById('status');
  const submit = document.getElementById('submit');

  const setStatus = (message, kind = '') => {
    status.textContent = message;
    status.className = `status ${kind}`.trim();
  };

  if (!tg) {
    setStatus('Open this page from the Telegram bot /add_target button.', 'error');
    submit.disabled = true;
    return;
  }

  tg.ready();
  tg.expand();

  if (!tg.initData) {
    setStatus('Telegram authorization data is unavailable. Re-open from Telegram.', 'error');
    submit.disabled = true;
    return;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const payload = {
      version: 1,
      action: 'add_target',
      initData: tg.initData,
      target: {
        site_key: document.getElementById('site-key').value.trim(),
        target_url: document.getElementById('target-url').value.trim(),
        data_selector: document.getElementById('data-selector').value.trim(),
        extract_mode: document.getElementById('extract-mode').value,
        enabled: document.getElementById('enabled').checked
      }
    };

    const encoded = JSON.stringify(payload);
    if (encoded.length > 4096) {
      setStatus('Payload is too large.', 'error');
      return;
    }

    submit.disabled = true;
    setStatus('Sending securely to the Telegram bot…');
    try {
      tg.sendData(encoded);
      setStatus('Submitted. The bot will validate and update the target list.', 'ok');
    } catch (error) {
      setStatus('Telegram could not send the payload. Please try again.', 'error');
      submit.disabled = false;
    }
  });
})();
