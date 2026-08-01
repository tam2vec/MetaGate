(function () {
  const API_BASE = "http://127.0.0.1:8765";
  const CAPABILITY = "autonomous-agent-action";
  const PANEL_ID = "predicate-datahub-auto-panel";

  function extractUrn() {
    const match = window.location.pathname.match(/\/dataset\/([^/]+)/);
    if (!match) {
      return null;
    }
    try {
      return decodeURIComponent(match[1]);
    } catch (error) {
      return match[1];
    }
  }

  function assetName(urn) {
    const parts = urn.split(",");
    return parts.length > 1 ? parts[parts.length - 2] : urn;
  }

  function colorFor(decision) {
    return decision === "allowed" ? "#13824c" : "#bc3030";
  }

  function backgroundFor(decision) {
    return decision === "allowed" ? "#e8f7ee" : "#fff0f0";
  }

  function metricClass(value) {
    if (value === null || value === undefined || value === "n/a") {
      return "warn";
    }
    if (Number(value) >= 92) {
      return "strong";
    }
    if (Number(value) >= 85) {
      return "warn";
    }
    return "weak";
  }

  function failedTerms(run) {
    const predicate = run.predicate || run.action_predicate || {};
    return run.failed || predicate.failed_terms || [];
  }

  function remediationFor(run) {
    const name = assetName(run.urn || run.entity_urn || "");
    const assetMaps = {
      fct_users_created: {
        "assertions.present": "Add assertions: user_id not null, user_id unique per reporting day, daily signup row count in expected range, and signup freshness SLA passing.",
        "readiness_score >= 92.0": "Lift readiness by adding the missing signup assertions; other required evidence is already mostly present.",
        "confidence >= 88.0": "Use DataHub assertion run history as evidence, then rerun Predicate on fct_users_created."
      },
      fct_users_deleted: {
        "assertions.present": "Add assertions: deleted_at not null, deleted_at inside reporting day, deletion count anomaly threshold, and deleted users absent from active-user outputs.",
        "readiness_score >= 92.0": "Prioritize deletion-specific assertions because this asset can affect privacy and churn metrics.",
        "confidence >= 88.0": "Back deletion checks with DataHub assertion run history so the block is auditable."
      },
      SampleKafkaDataset: {
        "assertions.present": "Add stream checks: schema compatibility, consumer lag below threshold, payload parse failure rate, and topic freshness.",
        "readiness_score >= 92.0": "Kafka assets need stream-specific quality evidence before autonomous action.",
        "confidence >= 88.0": "Use live Kafka/schema-registry checks rather than static topic documentation."
      },
      customer_lifetime_value: {
        "glossary.present": "Add glossary terms: Customer Lifetime Value, Net Revenue Retention, Billing Account, Churn Probability, and Prediction Date.",
        "column_lineage.present": "Map customer_id from CRM, predicted_lifetime_value from billing/renewals/churn model/discounts, and prediction_date from the scoring job.",
        "assertions.present": "Resolve gross ARR vs net revenue conflict; add non-negative CLV, USD currency normalization, prediction date freshness, and model version checks.",
        "freshness.present": "Refresh the CLV scoring job or keep the asset blocked until prediction_date is inside the finance SLA.",
        "readiness_score >= 95.0": "Finance production policy requires 95 because autonomous actions can affect executive metrics.",
        "confidence >= 93.0": "Resolve contradictory revenue definitions and stale freshness before trusting this asset."
      }
    };
    const fallback = {
      "assertions.present": "Add asset-specific DataHub assertions for row count, nulls, uniqueness, freshness, and business invariants.",
      "column_lineage.present": "Complete column-level lineage for the fields an agent may summarize, transform, or modify.",
      "glossary.present": "Attach approved glossary terms that define the asset and its key columns.",
      "freshness.present": "Repair freshness evidence or update the SLA timestamp so it is inside policy.",
      "readiness_score >= 92.0": "Repair high-severity metadata gaps, then rerun Predicate.",
      "readiness_score >= 95.0": "Meet the stricter production readiness threshold before autonomous action.",
      "confidence >= 88.0": "Improve graph coverage and evidence source confidence.",
      "confidence >= 93.0": "Resolve stale or contradictory evidence to meet confidence requirements."
    };
    const map = assetMaps[name] || fallback;
    const terms = failedTerms(run);
    if (!terms.length) {
      return ["No repair required. Keep the certificate current when metadata changes."];
    }
    return terms.slice(0, 4).map((term) => map[term] || fallback[term] || `Repair failed term: ${term}.`);
  }

  function buildPanel(urn) {
    const panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.innerHTML = `
      <div class="predicate-card">
        <div class="predicate-heading">
          <div>
            <div class="predicate-kicker">Predicate</div>
            <h2>AI action check</h2>
          </div>
          <button class="predicate-close" type="button" aria-label="Close Predicate panel" title="Close Predicate panel">&times;</button>
        </div>
        <div class="predicate-status">Evaluating DataHub metadata...</div>
        <div class="predicate-body"></div>
      </div>
    `;
    const style = document.createElement("style");
    style.textContent = `
      #${PANEL_ID} {
        position: fixed;
        top: 92px;
        right: 22px;
        width: 360px;
        z-index: 2147483000;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #172033;
      }
      #${PANEL_ID} .predicate-card {
        background: #fff;
        border: 1px solid #dce3ee;
        border-radius: 10px;
        box-shadow: 0 18px 46px rgba(18, 31, 52, .18);
        padding: 16px;
      }
      #${PANEL_ID} .predicate-kicker {
        color: #617086;
        font-size: 12px;
        text-transform: uppercase;
        font-weight: 800;
      }
      #${PANEL_ID} .predicate-heading {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }
      #${PANEL_ID} h2 {
        margin: 3px 0 12px;
        font-size: 20px;
        letter-spacing: 0;
      }
      #${PANEL_ID} .predicate-close {
        width: 32px;
        height: 32px;
        flex: 0 0 32px;
        border: 1px solid #dce3ee;
        border-radius: 8px;
        background: #fff;
        color: #617086;
        cursor: pointer;
        font-size: 24px;
        line-height: 1;
      }
      #${PANEL_ID} .predicate-close:hover {
        background: #f5f7fb;
        color: #172033;
      }
      #${PANEL_ID} .predicate-status {
        border: 1px solid #dce3ee;
        border-radius: 8px;
        background: #f5f7fb;
        padding: 12px;
        font-size: 13px;
        line-height: 1.4;
        color: #617086;
      }
      #${PANEL_ID} .predicate-decision {
        border-radius: 8px;
        padding: 13px;
        margin-bottom: 10px;
      }
      #${PANEL_ID} .predicate-decision strong {
        display: block;
        font-size: 30px;
        text-transform: uppercase;
        margin: 3px 0;
      }
      #${PANEL_ID} .predicate-meta {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin: 10px 0;
      }
      #${PANEL_ID} .predicate-metric {
        border: 1px solid #dce3ee;
        border-radius: 8px;
        padding: 10px;
        background: #f5f7fb;
      }
      #${PANEL_ID} .predicate-metric span {
        display: block;
        color: #617086;
        font-size: 12px;
      }
      #${PANEL_ID} .predicate-metric strong {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 3px 9px;
        margin-top: 3px;
        font-size: 20px;
        font-weight: 900;
      }
      #${PANEL_ID} .predicate-metric strong.strong {
        background: #e8f7ee;
        color: #13824c;
      }
      #${PANEL_ID} .predicate-metric strong.warn {
        background: #fff6df;
        color: #a96d10;
      }
      #${PANEL_ID} .predicate-metric strong.weak {
        background: #fff0f0;
        color: #bc3030;
      }
      #${PANEL_ID} ol {
        margin: 8px 0 0;
        padding-left: 19px;
      }
      #${PANEL_ID} li {
        color: #617086;
        font-size: 13px;
        line-height: 1.4;
        margin: 5px 0;
      }
      #${PANEL_ID} .predicate-link {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 40px;
        margin-top: 12px;
        border-radius: 8px;
        background: #315fd8;
        color: white;
        text-decoration: none;
        font-weight: 800;
      }
      @media (max-width: 900px) {
        #${PANEL_ID} {
          left: 12px;
          right: 12px;
          top: auto;
          bottom: 12px;
          width: auto;
        }
      }
    `;
    document.documentElement.appendChild(style);
    (document.body || document.documentElement).appendChild(panel);
    panel.dataset.urn = urn;
    panel.querySelector(".predicate-close").addEventListener("click", () => {
      panel.dataset.dismissed = "true";
      panel.remove();
      window.__predicateDismissedUrl = location.href;
    });
    return panel;
  }

  function renderResult(panel, run) {
    const decision = run.decision || (run.allowed ? "allowed" : "blocked");
    const readiness = run.readiness ?? run.readiness_score ?? "n/a";
    const confidence = run.confidence ?? "n/a";
    const body = panel.querySelector(".predicate-body");
    const status = panel.querySelector(".predicate-status");
    status.remove();
    body.innerHTML = `
      <div class="predicate-decision" style="background:${backgroundFor(decision)}; color:${colorFor(decision)}">
        <span>${assetName(run.urn || run.entity_urn || "")}</span>
        <strong>${decision}</strong>
      </div>
      <div class="predicate-meta">
        <div class="predicate-metric"><span>Readiness</span><strong class="${metricClass(readiness)}">${readiness}</strong></div>
        <div class="predicate-metric"><span>Confidence</span><strong class="${metricClass(confidence)}">${confidence}</strong></div>
      </div>
      <div class="predicate-status">${run.reason || "Predicate evaluated this asset."}</div>
      <h3 style="font-size:14px; margin:12px 0 0;">Repair queue</h3>
      <ol>${remediationFor(run).map((item) => `<li>${item}</li>`).join("")}</ol>
      <a class="predicate-link" href="${API_BASE}/review" target="_blank" rel="noreferrer">Open Predicate Review</a>
    `;
  }

  function renderError(panel, message) {
    const status = panel.querySelector(".predicate-status");
    status.textContent = message;
  }

  async function evaluateCurrentAsset(force = false) {
    const urn = extractUrn();
    if (!urn) {
      document.getElementById(PANEL_ID)?.remove();
      window.__predicateDismissedUrl = null;
      return;
    }
    if (window.__predicateDismissedUrl === location.href) {
      return;
    }
    let panel = document.getElementById(PANEL_ID);
    if (panel && panel.dataset.urn === urn && !force) {
      return;
    }
    if (!panel || panel.dataset.urn !== urn) {
      if (panel) {
        panel.remove();
      }
      panel = buildPanel(urn);
    }
    try {
      const url = `${API_BASE}/api/evaluate?urn=${encodeURIComponent(urn)}&capability=${encodeURIComponent(CAPABILITY)}`;
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Predicate API returned ${response.status}`);
      }
      renderResult(panel, await response.json());
    } catch (error) {
      renderError(panel, "Start the local Predicate review server, then refresh this DataHub asset page.");
    }
  }

  evaluateCurrentAsset();
  let lastUrl = location.href;
  function handleUrlChange() {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      window.__predicateDismissedUrl = null;
      evaluateCurrentAsset();
    }
  }

  window.addEventListener("popstate", handleUrlChange);
  window.addEventListener("hashchange", handleUrlChange);
  // DataHub can update its router without emitting a history event. A short
  // URL-only check keeps navigation cleanup immediate without polling scores.
  setInterval(handleUrlChange, 50);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      window.__predicateDismissedUrl = null;
      return;
    }
    evaluateCurrentAsset(true);
  });
  for (const method of ["pushState", "replaceState"]) {
    const original = history[method];
    history[method] = function (...args) {
      const result = original.apply(this, args);
      handleUrlChange();
      return result;
    };
  }
  setInterval(() => evaluateCurrentAsset(true), 5000);
})();
