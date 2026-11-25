"use strict";

globalThis.SaigenDetailController = Object.freeze({
  create({
    query: $,
    escape: esc,
    getFlow,
    getState,
    getEvents,
    getHash,
    goBack,
    request,
    accept,
    toast,
    editor,
    firstPlot,
    firstTable,
    imagePreview,
    tableMarkup,
    displayText,
    displayCommand,
    displayRecord,
    shortDate,
    fileRows,
    workflows,
    planMarkup,
    terminalMarkup,
    bindOriginalCommands,
    openStateEditor,
    openState,
    openArtifact,
    bookmarkButton,
    toggleBookmark,
    groupPath,
    showGroupMembers,
    activeElement,
    getElementById,
  }) {
    const storyCache = new Map();
    const storyPending = new Set();
    function loadStory(id) {
      const flow = getFlow();
      const key = id + ":" + flow.revision;
      if (
        storyPending.has(key) ||
        storyCache.get(id)?.revision === flow.revision
      )
        return;
      storyPending.add(key);
      request("/api/story/" + encodeURIComponent(id))
        .then((story) => {
          if (story.revision !== getFlow().revision) return;
          storyCache.set(id, story);
          if (getHash() === "#state/" + encodeURIComponent(id)) {
            const top = $("#detail-view").scrollTop;
            renderDetail(getState(id) || story.state);
            $("#detail-view").scrollTop = top;
          }
        })
        .catch((error) => {
          if (flow.revision !== getFlow().revision) return;
          if (getHash() === "#state/" + encodeURIComponent(id)) {
            toast(error.message);
            $("#detail-content").innerHTML =
              '<button class="back" id="failed-story-back">← Back to flow</button><p>' +
              esc(error.message) +
              "</p>";
            $("#failed-story-back").onclick = () => goBack();
          }
        })
        .finally(() => storyPending.delete(key));
    }
    function renderDetail(n) {
      const flow = getFlow();
      if (!n) return;
      const restoreBookmarkFocus = activeElement?.()?.dataset.bookmark === n.id;
      const story =
        storyCache.get(n.id)?.revision === flow.revision
          ? storyCache.get(n.id)
          : null;
      loadStory(n.id);
      const incoming =
          story?.actions || flow.actions.filter((a) => a.to === n.id),
        plot = firstPlot(n),
        pending = n.status === "running";
      let visual = "";
      if (plot)
        visual =
          '<figure class="figure"><div class="figure-title">' +
          esc(plot.name) +
          "</div>" +
          imagePreview(n, "detail-image") +
          "<figcaption>Preserved output · SHA-256 " +
          esc(plot.sha256.slice(0, 16)) +
          "…</figcaption></figure>";
      else if (firstTable(n)) visual = tableMarkup(n);
      else if (pending)
        visual =
          '<div class="run-display"><div class="preview-label">' +
          esc(n.status) +
          "</div><p>" +
          "The recorder is waiting for the command to finish." +
          "</p></div>";
      else if (["failed", "cancelled", "unknown"].includes(n.status))
        visual =
          '<div class="run-display"><div class="preview-label">' +
          esc(n.status) +
          "</div><p>" +
          esc(
            displayText(
              incoming.find((a) => a.error)?.error ||
                "This attempt did not produce a verified completion record.",
            ),
          ) +
          "</p></div>";
      const origin =
        n.status === "planned"
          ? n.origin === "manual"
            ? "This is a human-supplied plan. No execution has been recorded."
            : "This is an agent-proposed plan. No execution has been recorded."
          : n.origin === "terminal"
            ? "Selected files were preserved at this checkpoint. Command order records session activity; it does not establish file dependencies."
            : n.status === "imported"
              ? "Existing files were recorded. Their earlier execution is not established by this import."
              : "Execution status was observed by the recorder. A successful command does not establish scientific correctness.";
      const parents = groupPath?.(n.id) ?? [];
      const breadcrumbs = parents.length
        ? '<nav class="detail-group-path" aria-label="Analysis group path">' +
          parents.map(group => '<button class="source-link" data-focus-group="' + esc(group.id) + '" title="Show group members on canvas">' +
            esc(group.title) + '</button>').join('<span aria-hidden="true">›</span>') +
          '</nav>'
        : '';
      const details = SaigenDetails.create({
        getFlow: () =>
          story?.archive ? { ...flow, actions: story.actions } : flow,
        escape: esc,
        fileRows,
        displayCommand,
        displayRecord,
        displayText,
        shortDate,
        workflows,
      }).render(n);
      $("#detail-content").innerHTML =
        '<nav class="detail-nav"><button class="back" id="back-flow">← Back to flow</button><div class="detail-tools"><button class="quiet" id="add-explanation">Add explanation</button>' +
        (story?.archive
          ? ""
          : '<button class="quiet" id="edit-detail">Edit state</button>') +
        '</div></nav>' + breadcrumbs + '<div class="detail-kicker">' +
        esc(story?.archive?.label || n.status) +
        '</div><div class="detail-heading"><h1 class="detail-title">' +
        esc(n.title) +
        '</h1>' +
        (getState(n.id) ? (bookmarkButton?.(n) ?? "") : "") +
        "</div>" +
        SaigenStory.create({ escape: esc, shortDate }).render(
          story,
          visual,
          {
            details,
            originalPlan: story?.originalPlan ? planMarkup(story.originalPlan) : "",
            executionPlan: story && n.plan ? planMarkup(n.plan) : "",
            terminal: terminalMarkup(n.terminal),
          },
        ) +
        details.reconstruction +
        (story
          ? SaigenVerification.create({
              escape: esc,
              shortDate,
              displayText,
              artifactName: (id) => flow.artifacts[id]?.name || id,
            }).render(story.verification)
          : "") +
        (story?.entries.length
          ? '<button class="quiet" id="correct-explanation">Correct a recorded explanation</button>'
          : "") +
        '<p class="origin-note">' +
        esc(origin) +
        "</p>";
      $("#detail-content").querySelectorAll("[data-focus-group]").forEach(button => {
        button.onclick = () => showGroupMembers(button.dataset.focusGroup);
      });
      $("#add-explanation").onclick = () => editor.open(n, story);
      $("#correct-explanation")?.addEventListener("click", () =>
        editor.open(n, story, true),
      );
      $("#detail-content")
        .querySelectorAll("[data-event-link],[data-entry-link]")
        .forEach(
          (link) =>
            (link.onclick = (event) => {
              event.preventDefault();
              const target = getElementById(
                link.dataset.eventLink
                  ? "event-" + link.dataset.eventLink
                  : "explanation-" + link.dataset.entryLink,
              );
              if (target) {
                for (
                  let parent = target.parentElement;
                  parent;
                  parent = parent.parentElement
                )
                  if (parent.tagName === "DETAILS") parent.open = true;
                target.querySelector("details")?.setAttribute("open", "");
                target.scrollIntoView({ block: "center" });
              } else if (link.dataset.eventLink) {
                const record = getEvents().find(
                  (e) => String(e.revision) === link.dataset.eventLink,
                );
                if (record) {
                  $("#artifact-title").textContent =
                    "Recorded event " + record.revision;
                  $("#artifact-body").innerHTML =
                    "<pre>" +
                    esc(JSON.stringify(displayRecord(record), null, 2)) +
                    "</pre>";
                  $("#artifact-dialog").showModal();
                } else toast("Referenced event is unavailable.");
              }
            }),
        );

      $("#detail-content")
        .querySelectorAll("[data-reconstruction]")
        .forEach(
          (button) =>
            (button.onclick = async () => {
              button.disabled = true;
              try {
                const next = await request(
                  "/api/reconstructions/" +
                    button.dataset.reconstruction +
                    "/" +
                    button.dataset.decision,
                  {
                    revision: getFlow().revision,
                    stateId: button.dataset.stateId,
                    connectionId: button.dataset.connectionId,
                    evidenceId: button.dataset.evidenceId,
                    reason:
                      $(
                        '[data-review-reason="' +
                          button.dataset.reconstruction +
                          '"]',
                      )?.value || "",
                  },
                );
                await accept(next);
              } catch (error) {
                toast(error.message);
                button.disabled = false;
              }
            }),
        );
      $("#detail-content")
        .querySelectorAll("[data-verify-approve]")
        .forEach(
          (button) =>
            (button.onclick = async () => {
              button.disabled = true;
              try {
                await accept(
                  await request(
                    "/api/verifications/" +
                      button.dataset.verifyApprove +
                      "/approve",
                    {
                      revision: getFlow().revision,
                      digest: button.dataset.digest,
                    },
                  ),
                );
                toast(
                  "Verification approval recorded. No command has started.",
                );
              } catch (error) {
                toast(error.message);
                button.disabled = false;
              }
            }),
        );
      bindOriginalCommands($("#detail-content"));
      $("#back-flow").onclick = () => goBack();
      const bookmark = $("#detail-content").querySelector("[data-bookmark]");
      if (bookmark) {
        bookmark.onclick = () => toggleBookmark(bookmark);
        if (restoreBookmarkFocus) bookmark.focus({preventScroll: true});
      }
      $("#edit-detail")?.addEventListener("click", () => openStateEditor(n));
      $("#detail-content")
        .querySelectorAll("[data-open]")
        .forEach((b) => (b.onclick = () => openState(b.dataset.open)));
      $("#detail-content")
        .querySelectorAll("[data-artifact]")
        .forEach((b) => (b.onclick = () => openArtifact(b.dataset.artifact)));
    }
    async function openArchive() {
      try {
        const archived = await request("/api/archive");
        $("#archive-body").innerHTML = archived.length
          ? archived
              .map(
                (n) =>
                  '<p><button class="source-link" data-archive-state="' +
                  esc(n.id) +
                  '">' +
                  esc(n.title) +
                  "</button> · " +
                  esc(n.label) +
                  "</p>",
              )
              .join("")
          : "<p>No archived work recorded.</p>";
        $("#archive-body")
          .querySelectorAll("[data-archive-state]")
          .forEach(
            (button) =>
              (button.onclick = () => {
                $("#archive-dialog").close();
                openState(button.dataset.archiveState);
              }),
          );
        $("#archive-dialog").showModal();
      } catch (error) {
        toast(error.message);
      }
    }
    $("#close-archive").onclick = () => $("#archive-dialog").close();

    return Object.freeze({
      load: loadStory,
      render: renderDetail,
      openArchive,
      state: (id) => storyCache.get(id)?.state,
    });
  },
});
