"use strict";

const CONFIG = {
  brain: "../memory/brain.json",
  targets: "../input/targets.json",
  errors: "../memory/error_log.json"
};

const elements = {
  connectionStatus: document.getElementById("connectionStatus"),
  refreshButton: document.getElementById("refreshButton"),
  lastRun: document.getElementById("lastRun"),
  systemStatus: document.getElementById("systemStatus"),
  systemStatusMeta: document.getElementById("systemStatusMeta"),
  targetCount: document.getElementById("targetCount"),
  enabledTargetCount: document.getElementById("enabledTargetCount"),
  errorCount: document.getElementById("errorCount"),
  targetsState: document.getElementById("targetsState"),
  targetsBody: document.getElementById("targetsBody"),
  errorsState: document.getElementById("errorsState"),
  errorsContainer: document.getElementById("errorsContainer")
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function maskSensitiveText(value) {
  if (!value) return "";
  let text = String(value);
  text = text.replace(/bot\d+:[A-Za-z0-9_-]{20,}/gi, "[REDACTED]");
  text = text.replace(/(?:token|secret|password|api[_-]?key|authorization)\s*[:=]\s*[^\s,;"']+/gi, "[REDACTED]");
  text = text.replace(/gh[pousr]_[A-Za-z0-9_]{20,}/g, "[REDACTED]");
  text = text.replace(/AIza[0-9A-Za-z_-]{20,}/g, "[REDACTED]");
  return text;
}

async function fetchJson(path) {
  const response = await fetch(`${path}?v=${Date.now()}`, {
    method: "GET",
    cache: "no-store",
    headers: { Accept: "application/json" }
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function findLastRun(value) {
  if (!value || typeof value !== "object") return null;
  const preferredKeys = ["last_run", "last_run_at", "lastRun", "lastRunAt", "last_executed_run", "last_executed_at", "last_execution", "last_execution_at", "updated_at"];
  for (const key of preferredKeys) {
    if (typeof value[key] === "string" || typeof value[key] === "number") return value[key];
  }
  for (const key of ["run", "execution", "worker", "state", "status", "meta"]) {
    if (value[key] && typeof value[key] === "object") {
      const nested = findLastRun(value[key]);
      if (nested) return nested;
    }
  }
  return null;
}

function formatTimestamp(value) {
  if (value === null || value === undefined || value === "") return "No run recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(maskSensitiveText(value));
  return escapeHtml(date.toLocaleString());
}

function renderBrain(brain) {
  const lastRun = findLastRun(brain);
  elements.lastRun.textContent = lastRun ? formatTimestamp(lastRun) : "No run recorded";
  elements.systemStatus.textContent = lastRun ? "Active" : "Idle";
  elements.systemStatusMeta.textContent = lastRun ? "Last execution detected" : "Waiting for an execution record";
}

function renderTargets(targets) {
  if (!Array.isArray(targets)) throw new Error("targets.json is invalid");
  const enabledCount = targets.filter((target) => target && target.enabled === true).length;
  elements.targetCount.textContent = String(targets.length);
  elements.enabledTargetCount.textContent = `${enabledCount} active`;
  elements.targetsState.textContent = `${targets.length} target${targets.length === 1 ? "" : "s"}`;

  if (targets.length === 0) {
    elements.targetsBody.innerHTML = '<tr><td colspan="4" class="empty-cell">No targets configured.</td></tr>';
    return;
  }

  elements.targetsBody.innerHTML = targets.map((target) => {
    const siteKey = escapeHtml(target?.site_key || "—");
    const url = escapeHtml(target?.target_url || "—");
    const extract = escapeHtml(target?.task?.extract || "text");
    const enabled = target?.enabled === true;
    return `<tr>
      <td><strong>${siteKey}</strong></td>
      <td class="url">${url}</td>
      <td><span class="mode-badge">${extract}</span></td>
      <td><span class="target-status ${enabled ? "active" : "disabled"}">${enabled ? "Active" : "Disabled"}</span></td>
    </tr>`;
  }).join("");
}

function renderErrors(errors) {
  if (!Array.isArray(errors)) throw new Error("error_log.json is invalid");
  elements.errorCount.textContent = String(errors.length);
  elements.errorsState.textContent = `${errors.length} entr${errors.length === 1 ? "y" : "ies"}`;

  if (errors.length === 0) {
    elements.errorsContainer.innerHTML = '<div class="empty-state">No errors recorded.</div>';
    return;
  }

  elements.errorsContainer.innerHTML = [...errors].reverse().map((error) => {
    const timestamp = escapeHtml(error?.timestamp || "Unknown time");
    const stage = escapeHtml(error?.stage || "Unknown stage");
    const siteKey = escapeHtml(error?.site_key || "—");
    const message = escapeHtml(maskSensitiveText(error?.error || "Unknown error"));
    return `<article class="error-card">
      <div class="error-header"><span class="error-stage">${stage}</span><span class="error-time">${timestamp}</span></div>
      <div class="error-site"><strong>Site:</strong> ${siteKey}</div>
      <div class="error-message"><strong>Error:</strong> ${message}</div>
    </article>`;
  }).join("");
}

function setConnectionStatus(success, message) {
  elements.connectionStatus.className = `status-badge ${success ? "online" : "error"}`;
  elements.connectionStatus.textContent = message;
}

async function loadDashboard() {
  elements.refreshButton.disabled = true;
  elements.connectionStatus.className = "status-badge loading";
  elements.connectionStatus.textContent = "Loading";
  elements.targetsState.textContent = "Loading";
  elements.errorsState.textContent = "Loading";

  try {
    const [brain, targets, errors] = await Promise.all([
      fetchJson(CONFIG.brain),
      fetchJson(CONFIG.targets),
      fetchJson(CONFIG.errors)
    ]);
    renderBrain(brain);
    renderTargets(targets);
    renderErrors(errors);
    setConnectionStatus(true, "Operational");
  } catch (error) {
    console.error("Dashboard loading failed:", error);
    setConnectionStatus(false, "Unavailable");
    elements.systemStatus.textContent = "Unavailable";
    elements.systemStatusMeta.textContent = "Dashboard data could not be loaded";
    elements.lastRun.textContent = "Unavailable";
    elements.targetsState.textContent = "Unavailable";
    elements.targetsBody.innerHTML = '<tr><td colspan="4" class="empty-cell">Unable to load target data.</td></tr>';
    elements.errorsState.textContent = "Unavailable";
    elements.errorsContainer.innerHTML = '<div class="empty-state">Unable to load error log.</div>';
    elements.targetCount.textContent = "—";
    elements.enabledTargetCount.textContent = "Unavailable";
    elements.errorCount.textContent = "—";
  } finally {
    elements.refreshButton.disabled = false;
  }
}

elements.refreshButton.addEventListener("click", loadDashboard);
loadDashboard();
