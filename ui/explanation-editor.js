"use strict";

globalThis.SaigenExplanationEditor = Object.freeze({
  create({
    query: $,
    escape: esc,
    field,
    getFlow,
    request,
    accept,
    toast,
    FormData,
  }) {
    let explanationContext = null;
    function openExplanation(n, story, correct = false, previous = null) {
      const flow = getFlow();
      const entries = (story?.entries || []).filter((e) => !e.supersededBy);
      if (correct && !previous) previous = entries[0];
      if (correct && !previous) {
        toast("No current explanation to correct.");
        return;
      }
      explanationContext = { state: n.id, previous, revision: flow.revision };
      const e = previous || {},
        select = (name, label, values, value) =>
          '<label class="field">' +
          label +
          '<select name="' +
          name +
          '">' +
          values
            .map(
              ([v, t]) =>
                '<option value="' +
                esc(v) +
                '"' +
                (v === value ? " selected" : "") +
                ">" +
                esc(t) +
                "</option>",
            )
            .join("") +
          "</select></label>";
      const participant = (p) =>
        '<div class="story-form-row">' +
        field("participantName", "Name (declared)", p.name || "") +
        select(
          "participantRole",
          "Role",
          ["proposer", "contributor", "approver", "executor", "recorder"].map(
            (v) => [v, v],
          ),
          p.role || "contributor",
        ) +
        '<button type="button" data-remove-row>Remove</button></div>';
      const alternative = (a) =>
        '<div class="story-form-row">' +
        field("alternativeOption", "Alternative", a.option || "") +
        field("alternativeReason", "Reason / tradeoff", a.reason || "") +
        '<button type="button" data-remove-row>Remove</button></div>';
      const kinds = [
        ["question", "Scientific question"],
        ["finding", "Finding"],
        ["interpretation", "Interpretation"],
        ["limitation", "Limitation"],
        ["decision", "Decision"],
        ["replacement", "Replacement relationship"],
      ];
      $("#explanation-title").textContent = correct
        ? "Correct explanation"
        : "Add explanation";
      $("#explanation-error").textContent = "";
      $("#explanation-fields").innerHTML =
        (correct
          ? select(
              "correction",
              "Statement to correct",
              entries.map((v) => [v.id, v.summary]),
              e.id,
            )
          : "") +
        select(
          "kind",
          "Type",
          correct ? kinds.filter(([kind]) => kind === e.kind) : kinds,
          e.kind || "interpretation",
        ) +
        field("summary", "Summary", e.summary || "", "textarea") +
        select(
          "action",
          "Applies to",
          [
            ["", "Whole state"],
            ...(story?.actions || []).map((a) => [a.id, a.label || a.id]),
          ],
          e.actions?.[0] || "",
        ) +
        '<div id="decision-fields">' +
        field("rationale", "Rationale", e.rationale || "", "textarea") +
        field(
          "agreementBasis",
          "Basis for agreement",
          e.agreementBasis || "",
          "textarea",
        ) +
        '<h3>Alternatives considered</h3><div id="alternative-rows">' +
        (e.alternatives || []).map(alternative).join("") +
        '</div><button type="button" id="add-alternative">+ Alternative</button></div>' +
        '<div id="replacement-fields">' +
        select(
          "replacementStateId",
          "Replacement result or proposal",
          flow.states.filter((s) => s.id !== n.id).map((s) => [s.id, s.title]),
          e.replacementStateId || "",
        ) +
        '<p class="edit-notice">Use the summary to explain why. This link preserves the original attempt and its status.</p></div>' +
        select(
          "evidenceKind",
          "Evidence classification",
          [
            ["reported", "Reported statement"],
            ["direct", "Direct evidence"],
            ["inferred", "Inferred explanation"],
            ["unresolved", "Unresolved"],
          ],
          e.evidenceKind || "reported",
        ) +
        "<h3>Supporting evidence</h3>" +
        (e.evidence?.length
          ? "<p>Existing references will be retained.</p>"
          : "") +
        select(
          "source",
          "Add a source",
          [
            ["", "None"],
            ...Object.values(flow.artifacts).map((a) => [
              "artifact:" + a.id,
              a.name,
            ]),
            ...flow.states.map((s) => ["state:" + s.id, s.title]),
          ],
          "",
        ) +
        field(
          "location",
          "Source location (lines, section, or panel)",
          "",
          "input",
          "For example: lines 42–45",
        ) +
        field(
          "historicalAt",
          "Historical date, if known (with timezone)",
          e.historicalAt || "",
          "input",
          "2026-11-17T10:00:00+04:00",
        ) +
        '<h3>Participants (optional, declared)</h3><div id="participant-rows">' +
        (e.participants || []).map(participant).join("") +
        '</div><button type="button" id="add-participant">+ Participant</button>';
      const update = () => {
        const kind = $("#explanation-fields [name=kind]").value;
        $("#decision-fields").hidden = kind !== "decision";
        $("#replacement-fields").hidden = kind !== "replacement";
      };
      update();
      $("#explanation-fields [name=kind]").onchange = update;
      $("#explanation-fields [name=correction]")?.addEventListener(
        "change",
        (event) =>
          openExplanation(
            n,
            story,
            true,
            entries.find((v) => v.id === event.target.value),
          ),
      );
      $("#add-alternative").onclick = () =>
        $("#alternative-rows").insertAdjacentHTML("beforeend", alternative({}));
      $("#add-participant").onclick = () =>
        $("#participant-rows").insertAdjacentHTML("beforeend", participant({}));
      $("#explanation-fields").onclick = (event) => {
        if (event.target.matches("[data-remove-row]"))
          event.target.closest(".story-form-row").remove();
      };
      if (!$("#explanation-dialog").open) $("#explanation-dialog").showModal();
    }
    $("#close-explanation").onclick = () => $("#explanation-dialog").close();
    $("#explanation-form").onsubmit = async (event) => {
      event.preventDefault();
      const data = new FormData(event.target),
        context = explanationContext,
        kind = data.get("kind");
      const entry = {
        kind,
        states: context.previous?.states || [context.state],
        summary: data.get("summary"),
        evidenceKind: data.get("evidenceKind"),
        actions:
          context.previous?.actions?.length > 1
            ? context.previous.actions
            : data.get("action")
              ? [data.get("action")]
              : [],
        participants: data
          .getAll("participantName")
          .map((name, index) => ({
            name,
            role: data.getAll("participantRole")[index],
          }))
          .filter((p) => p.name.trim()),
        evidence: [...(context.previous?.evidence || [])],
      };
      if (kind === "decision") {
        entry.rationale = data.get("rationale");
        entry.agreementBasis = data.get("agreementBasis");
        entry.alternatives = data
          .getAll("alternativeOption")
          .map((option, index) => ({
            option,
            reason: data.getAll("alternativeReason")[index],
          }));
      }
      if (kind === "replacement")
        entry.replacementStateId = data.get("replacementStateId");
      if (data.get("historicalAt"))
        entry.historicalAt = data.get("historicalAt");
      if (context.previous) entry.supersedes = context.previous.id;
      if (data.get("source")) {
        const [type, id] = data.get("source").split(":");
        entry.evidence.push({ type, id, location: data.get("location") });
      }
      const submit = event.target.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        const next = await request("/api/explanations", {
          entry,
          revision: context.revision,
        });
        $("#explanation-dialog").close();
        await accept(next);
        toast("Explanation recorded. Earlier history preserved.");
      } catch (error) {
        $("#explanation-error").textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    };

    return Object.freeze({ open: openExplanation });
  },
});
