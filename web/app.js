"use strict";

const CONFIG={targets:"../input/targets.json",errors:"../memory/error_log.json"};
const elements={connectionStatus:document.getElementById("connectionStatus"),refreshButton:document.getElementById("refreshButton"),lastUpdated:document.getElementById("lastUpdated"),dashboardStatus:document.getElementById("dashboardStatus"),targetCount:document.getElementById("targetCount"),enabledTargetCount:document.getElementById("enabledTargetCount"),errorCount:document.getElementById("errorCount"),errorsState:document.getElementById("errorsState"),errorsContainer:document.getElementById("errorsContainer")};

function escapeHtml(value){return String(value??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}

function maskSensitiveText(value){if(!value)return "";let text=String(value);text=text.replace(/bot\d+:[A-Za-z0-9_-]{20,}/gi,"[REDACTED]");text=text.replace(/(?:token|secret|password|api[_-]?key|authorization)\s*[:=]\s*[^\s,;"']+/gi,"[REDACTED]");text=text.replace(/gh[pousr]_[A-Za-z0-9_]{20,}/g,"[REDACTED]");text=text.replace(/AIza[0-9A-Za-z_-]{20,}/g,"[REDACTED]");return text;}

async function fetchJson(path){const response=await fetch(`${path}?v=${Date.now()}`,{method:"GET",cache:"no-store",headers:{Accept:"application/json"}});if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();}

function renderTargets(targets){if(!Array.isArray(targets))throw new Error("targets.json is invalid");const enabledCount=targets.filter(target=>target&&target.enabled===true).length;elements.targetCount.textContent=String(targets.length);elements.enabledTargetCount.textContent=`${enabledCount} enabled`;}

function renderErrors(errors){if(!Array.isArray(errors))throw new Error("error_log.json is invalid");elements.errorCount.textContent=String(errors.length);elements.errorsState.textContent=`${errors.length} entr${errors.length===1?"y":"ies"}`;if(errors.length===0){elements.errorsContainer.innerHTML='<div class="empty-state">No errors recorded.</div>';return;}elements.errorsContainer.innerHTML=[...errors].reverse().map(error=>{const timestamp=escapeHtml(error?.timestamp||"Unknown time");const stage=escapeHtml(error?.stage||"Unknown stage");const siteKey=escapeHtml(error?.site_key||"—");const message=escapeHtml(maskSensitiveText(error?.error||"Unknown error"));return `<article class="error-card"><div class="error-header"><span class="error-stage">${stage}</span><span class="error-time">${timestamp}</span></div><div class="error-site"><strong>Site:</strong> ${siteKey}</div><div class="error-message"><strong>Error:</strong> ${message}</div></article>`;}).join("");}

function setConnectionStatus(success,message){elements.connectionStatus.className=`status-badge ${success?"online":"error"}`;elements.connectionStatus.textContent=message;elements.dashboardStatus.textContent=success?"Online":"Unavailable";}

async function loadDashboard(){elements.refreshButton.disabled=true;setConnectionStatus(true,"Loading...");elements.errorsState.textContent="Loading...";try{const [targets,errors]=await Promise.all([fetchJson(CONFIG.targets),fetchJson(CONFIG.errors)]);renderTargets(targets);renderErrors(errors);elements.lastUpdated.textContent=new Date().toLocaleString();setConnectionStatus(true,"Online");}catch(error){console.error("Dashboard loading failed:",error);setConnectionStatus(false,"Load failed");elements.errorsState.textContent="Unavailable";elements.errorsContainer.innerHTML='<div class="empty-state">Unable to load dashboard data.</div>';elements.targetCount.textContent="—";elements.enabledTargetCount.textContent="Unavailable";}finally{elements.refreshButton.disabled=false;}}

elements.refreshButton.addEventListener("click",loadDashboard);loadDashboard();
