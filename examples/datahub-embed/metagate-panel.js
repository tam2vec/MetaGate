(function () {
  function formatMetric(value) {
    return value === null || value === undefined ? "n/a" : Number(value).toFixed(2);
  }

  function createMetaGatePanel(decision) {
    var allowed = Boolean(decision.allowed);
    var status = allowed ? "allowed" : "blocked";
    var color = allowed ? "#13824c" : "#bc3030";
    var background = allowed ? "#e8f7ee" : "#fff0f0";
    var failedTerms = (
      decision.action_metagate && decision.action_metagate.failed_terms
        ? decision.action_metagate.failed_terms
        : []
    );

    var root = document.createElement("section");
    root.setAttribute("data-metagate-panel", "true");
    root.style.border = "1px solid #dce3ee";
    root.style.borderRadius = "8px";
    root.style.background = "#ffffff";
    root.style.padding = "16px";
    root.style.fontFamily = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";
    root.style.color = "#172033";
    root.style.boxShadow = "0 10px 26px rgba(18,31,52,.08)";

    root.innerHTML = [
      "<div style='color:#617086;font-size:12px;font-weight:800;text-transform:uppercase'>MetaGate</div>",
      "<h3 style='font-size:18px;margin:6px 0 14px'>AI action check</h3>",
      "<div style='border:1px solid #dce3ee;border-radius:8px;padding:14px;background:" + background + "'>",
      "<div style='font-size:12px;color:#617086'>autonomous-agent-action</div>",
      "<strong style='display:block;font-size:28px;text-transform:uppercase;color:" + color + ";margin-top:4px'>" + status + "</strong>",
      "<p style='font-size:13px;line-height:1.4;color:#617086;margin:7px 0 0'>" + decision.reason + "</p>",
      "</div>",
      "<div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px'>",
      "<div style='border:1px solid #dce3ee;border-radius:8px;padding:10px;background:#f5f7fb'><span style='font-size:12px;color:#617086'>Readiness</span><strong style='display:block;font-size:20px;margin-top:3px'>" + formatMetric(decision.readiness_score) + "</strong></div>",
      "<div style='border:1px solid #dce3ee;border-radius:8px;padding:10px;background:#f5f7fb'><span style='font-size:12px;color:#617086'>Confidence</span><strong style='display:block;font-size:20px;margin-top:3px'>" + formatMetric(decision.confidence) + "</strong></div>",
      "</div>",
      "<div style='margin-top:12px;font-size:13px;color:#617086'><strong style='display:block;color:#172033;margin-bottom:5px'>Failed terms</strong>" + (failedTerms.length ? failedTerms.join("<br>") : "None") + "</div>",
      "<a href='#metagate-full-review' style='display:flex;justify-content:center;align-items:center;height:40px;border-radius:8px;background:#315fd8;color:white;text-decoration:none;font-weight:800;margin-top:14px'>Open Full Review</a>"
    ].join("");

    return root;
  }

  window.MetaGatePanel = {
    create: createMetaGatePanel
  };
})();
