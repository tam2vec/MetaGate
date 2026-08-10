const DEFAULT_API_BASE = "http://127.0.0.1:8765";
const input = document.getElementById("apiBase");
const status = document.getElementById("status");

chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE }, (settings) => {
  const saved = String(settings.apiBase || DEFAULT_API_BASE).replace(/\/$/, "");
  const normalized = /^https?:\/\/(localhost|127\.0\.0\.1):8766$/i.test(saved)
    ? DEFAULT_API_BASE
    : saved;
  input.value = normalized;
  if (normalized !== saved) chrome.storage.sync.set({ apiBase: normalized });
});

document.getElementById("save").addEventListener("click", () => {
  const apiBase = input.value.trim().replace(/\/$/, "");
  try { new URL(apiBase); } catch { status.textContent = "Enter a valid URL."; return; }
  chrome.storage.sync.set({ apiBase }, () => {
    status.textContent = "Saved. Open or refresh a DataHub asset page.";
  });
});
