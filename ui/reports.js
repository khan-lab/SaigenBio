"use strict";

// Selection belongs to the canvas; jobs retain their own frozen snapshot.
globalThis.SaigenReports = Object.freeze({
  create({
    query: $,
    getFlow,
    getToken,
    request,
    render,
    hidePopups,
    clearSelection,
    toast,
  }) {
    let reportMode = false,
      reportSelection = [],
      reportJob = null,
      reportRendering = false,
      reportPreview = null;
    const getState = (id) => getFlow().states.find((n) => n.id === id);
    const esc = (v) =>
      String(v ?? "").replace(
        /[&<>"']/g,
        (c) =>
          ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
          })[c],
      );
    function panel(status, message = "", logAvailable = false) {
      const labels = {
        preparing: "Preparing report…",
        queued: "Report queued…",
        rendering: "Generating PDF…",
        ready: "PDF ready",
        failed: "Generation failed",
        unavailable: "Report status unavailable",
      };
      $("#report-progress").hidden = false;
      $("#report-status").textContent =
        labels[status] || "Checking report status…";
      $("#report-progress").classList.toggle(
        "processing",
        ["preparing", "queued", "rendering"].includes(status),
      );
      $("#report-error").textContent = message;
      $("#report-pdf").hidden = status !== "ready";
      $("#report-source").hidden = status !== "ready";
      $("#report-log").hidden = status !== "failed" || !logAvailable;
      $("#report-dismiss").hidden = reportRendering;
    }
    function setReportMode(value) {
      if (reportRendering) return;
      reportMode = value;
      clearSelection();
      $("#viewport").classList.remove("connecting");
      $("#viewport").classList.toggle("editing", !value);
      $("#edit-tools").hidden = value;
      if (value) location.hash = "";
      else {
        reportSelection = [];
        invalidateReport();
      }
      hidePopups();
      $("#report-toggle").setAttribute("aria-pressed", String(value));
      $("#viewport").classList.toggle("report-mode", value);
      render();
    }
    function toggleReportState(id) {
      if (reportRendering) return;
      invalidateReport();
      reportSelection = reportSelection.includes(id)
        ? reportSelection.filter((x) => x !== id)
        : [...reportSelection, id];
      hidePopups();
      render();
    }
    function invalidateReport() {
      reportPreview = null;
      $("#report-preview").close();
    }
    function renderReport() {
      if (!reportRendering && !reportPreview) {
        reportSelection = reportSelection.filter((id) => getState(id));
      }
      $("#report-tools").hidden = !reportMode;
      $("#report-count").textContent = reportSelection.length
        ? reportSelection.length +
          (reportSelection.length === 1
            ? " state selected"
            : " states selected")
        : "Select states in report order";
      $("#report-create").disabled = !reportSelection.length || reportRendering;
      $("#report-template").disabled = reportRendering;
      $("#report-cancel").disabled = reportRendering;
      $("#report-toggle").disabled = reportRendering || !getToken();
    }
    $("#report-toggle").onclick = () => setReportMode(!reportMode);
    $("#report-cancel").onclick = () => setReportMode(false);
    $("#report-template").onchange = () => {
      invalidateReport();
      renderReport();
    };
    $("#report-preview-close").onclick = () => $("#report-preview").close();
    $("#report-dismiss").onclick = () => {
      if (!reportRendering) $("#report-progress").hidden = true;
    };
    $("#report-create").onclick = async () => {
      if (reportRendering || !reportSelection.length) return;
      const selection = [...reportSelection],
        revision = getFlow().revision,
        template = $("#report-template").value;
      // Exit selection mode during preparation so ordinary canvas editing remains available.
      setReportMode(false);
      reportRendering = true;
      reportJob = null;
      reportPreview = null;
      renderReport();
      panel("preparing");
      try {
        const preview = await request("/api/reports/preview", {
          revision,
          selected: selection,
          template,
        });
        reportPreview = preview;
        reportJob = preview.id;
        $("#report-preview-body").innerHTML =
          "<p><strong>" +
          esc(preview.template.name) +
          "</strong></p><p>" +
          esc(preview.template.description) +
          '</p><p class="report-preview-hint">Contents outline. Export uses this frozen selection even if the canvas changes.</p><ol>' +
          preview.outline
            .map(
              (n) =>
                "<li><h3>" +
                esc(n.title) +
                '</h3><span class="preview-label">' +
                esc(n.status) +
                "</span><ul>" +
                n.sections.map((s) => "<li>" + esc(s) + "</li>").join("") +
                "</ul>" +
                (n.inclusionIssues || [])
                  .map(
                    (issue) =>
                      '<p class="report-inclusion-issue">' +
                      esc(issue) +
                      "</p>",
                  )
                  .join("") +
                "</li>",
            )
            .join("") +
          "</ol>";
        $("#report-progress").hidden = true;
        $("#report-preview").showModal();
      } catch (error) {
        panel("failed", error.message);
      } finally {
        reportRendering = false;
        $("#report-dismiss").hidden = false;
        renderReport();
      }
    };
    $("#report-export").onclick = async () => {
      if (!reportPreview || reportRendering) return;
      const preview = reportPreview;
      reportRendering = true;
      renderReport();
      $("#report-preview").close();
      panel("preparing");
      try {
        const job = await request("/api/reports/" + preview.id + "/render", {
          revision: preview.revision,
        });
        reportJob = job.id;
        await watchReport(job.id);
      } catch (error) {
        reportRendering = false;
        panel("failed", error.message);
        renderReport();
      }
    };
    async function watchReport(ident) {
      try {
        const response = await fetch("/api/reports/" + ident, {
          headers: { "X-Saigen-Token": getToken() },
        });
        const job = await response.json();
        if (!response.ok) throw new Error(job.error);
        if (ident !== reportJob) return;
        if (job.status === "ready" || job.status === "failed") {
          reportRendering = false;
          panel(job.status, job.error || "", job.logAvailable);
          renderReport();
          return;
        }
        panel(job.status);
        setTimeout(() => watchReport(ident), 1000);
      } catch (error) {
        panel("unavailable", "Retrying status check: " + error.message);
        setTimeout(() => watchReport(ident), 1000);
      }
    }
    async function downloadReport(kind) {
      try {
        const response = await fetch("/api/reports/" + reportJob + "/" + kind, {
          headers: { "X-Saigen-Token": getToken() },
        });
        if (!response.ok) throw new Error((await response.json()).error);
        const url = URL.createObjectURL(await response.blob()),
          link = document.createElement("a");
        link.href = url;
        link.download =
          kind === "log" ? "saigen-render.log" : "saigen-report." + kind;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
      } catch (error) {
        toast(error.message);
      }
    }
    $("#report-pdf").onclick = () => downloadReport("pdf");
    $("#report-source").onclick = () => downloadReport("zip");
    $("#report-log").onclick = () => downloadReport("log");
    return Object.freeze({
      get active() {
        return reportMode;
      },
      position: (id) => reportSelection.indexOf(id),
      setMode: setReportMode,
      toggleState: toggleReportState,
      render: renderReport,
    });
  },
});
