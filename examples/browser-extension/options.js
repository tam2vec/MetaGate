const DEFAULT_API_BASE = "http://127.0.0.1:8765";
const input = document.getElementById("apiBase");
const status = document.getElementById("status");

chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE }, (settings) => {
  input.value = settings.apiBase;
});

document.getElementById("save").addEventListener("click", () => {
  const apiBase = input.value.trim().replace(/\/$/, "");
  try { new URL(apiBase); } catch { status.textContent = "Enter a valid URL."; return; }
  chrome.storage.sync.set({ apiBase }, () => {
    status.textContent = "Saved. Open or refresh a DataHub asset page.";
  });
});
