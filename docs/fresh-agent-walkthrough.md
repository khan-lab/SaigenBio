# Test SaigenBio in a fresh AI-agent session

This walkthrough checks that an installed copy works outside the source repository, that a new agent can discover its skill, and that recorded analysis appears in the viewer.

Use a small synthetic example first. This tests the product experience; it is not a biological validation.

## Expected live behavior

Without planning: when the agent starts an analysis through the wrapper, a dotted result node describes its expected output and an animated edge travels toward it. On completion, the same node and edge become solid and the actual figure takes priority. Failed runs remain visibly failed.

With planning: the agent publishes proposed output nodes and presents the scientific plan in chat. Planned nodes have no execution edges. After you approve execution, each step starts its incoming animated edge and finalizes its own result in turn. Remaining proposals stay dotted. Plans reach the canvas through explicit agent recording commands; chat alone does not synchronize them. Native agent modes that forbid writes also prevent publishing canvas proposals until writes are allowed.

## 1. Build a fresh external trial

A verified installation of this version is ready at:

```text
/path/to/trial/workspace
```

Use that workspace directly, or build another trial below.

Build the current version so the CLI, web assets, and skill all include the live planning behavior. Run from the source repository:

```bash
python3 -B scripts/check_installation.py --with-quarto
```

Use the **Fresh-session workspace** path printed at the end:

```bash
cd /path/printed/by/the/check/workspace
source ../runtime/bin/activate
saigen --version
command -v saigen
```

The executable should be inside this trial's runtime/bin/. Keep the remaining commands in this workspace. Older trials do not automatically receive updated skills or project instructions.

The checker prepares two different instruction layers:

- AGENTS.md: the active analysis project, input location, viewer port, and instruction to use the recording skill.
- .agents/skills/saigen-record/SKILL.md: how to preserve and record analysis.

This is one-time workspace setup. Users do not need to repeat recording instructions in scientific prompts. The workspace AGENTS.md follows [Codex project instruction conventions](https://developers.openai.com/codex/guides/agents-md).

## 2. Prepare an empty project and open its viewer

```bash
saigen init --project projects/agent-demo-01 --name "Fresh agent demo"
saigen serve --project projects/agent-demo-01 --port 8767
```

Leave this terminal running. Open <http://127.0.0.1:8767/>.

This uses a separate port from the existing viewer on 8765. If 8767 is occupied, choose another free port and change the browser address accordingly; do not stop an unrelated server.

For another rehearsal, use a new project name such as `agent-demo-02` throughout these instructions and update AGENTS.md to match. If you change the viewer port, update it there too. Do not overwrite an earlier recorded analysis.

## 3. Start a fresh agent in the same workspace

Open another terminal:

```bash
cd /path/printed/by/the/check/workspace
source ../runtime/bin/activate
codex
```

Use a new conversation, not a resumed session. If you use a graphical agent application, open this workspace as the project and start a new conversation there. Ask it to verify that it uses the trial's installed CLI; a graphical application may not inherit your terminal environment.

The installed skill has already been copied to:

```text
.agents/skills/saigen-record/SKILL.md
```

Check whether `saigen-record` appears in the agent's skill selector. If it is missing, record that as a discovery failure. Explicitly reading the file can help diagnose the issue, but does not count as successful automatic discovery.

## 4. Ask the agent to create the first result

Paste this into the fresh conversation:

```text
I want to explore this sample-count table. First, plot the count
for each sample in sample-name order and tell me what stands out.
Let's inspect that before deciding what to do next.
```

The setup identifies the available table as synthetic. The agent should locate it, import it, and record its analysis without being reminded about SaigenBio. No biological interpretation should be invented for these test counts.


Watch the browser while the agent works. Completed records should appear without a manual reload. A short command may finish too quickly for its running animation to be noticeable.

## 5. Ask for a second branch

After the first result is complete, paste:

```text
Can you also show the same counts from largest to smallest?
Keep the first plot so I can compare the two presentations.
```


Expected shape: one imported state with two result branches. The exact labels depend on the table and the agent's script. Reusing the imported table as the parent is appropriate for two independent presentations; a genuinely derived result should follow its actual dependency.

## Optional: test planning before execution

In a fresh project configured in AGENTS.md, ask:

> First, propose a plan to plot this table in sample-name order and then compare it with a plot sorted by count. Wait for my approval before running the analysis.

Check that proposed results appear as dotted nodes, with descriptions and no edges. Input import may appear as an existing-evidence state. Then say:

> Go ahead with that plan.

Watch the planned nodes become running and then completed individually. Each executed step adds its actual edge; nodes for later steps remain planned. A fast command may finish between browser polls, so a visible animation is not guaranteed for very short runs.

## 6. Check the viewer

- Both independent presentation branches start from the imported state.
- For direct execution, the wrapper publishes the running state before the command finishes.
- For a plan, proposals have no edges until execution starts.
- Arrow labels and details explain the command or option difference.
- Hovering each result prioritizes its figure.
- A state without a figure shows its summary.
- Clicking a state opens its detailed record and preserved files.
- Reasons and actor information match what the agent actually recorded.
- Before reporting completion, the agent checked the active project's flow and verified the new state, action, and preserved outputs. A standalone SVG without a recorded state fails this test.

If something is missing, keep the failed attempt and ask the agent to diagnose it. A retry should create a new recorded run.

## 7. Export a report

Quarto must be available to the viewer process. It was available during this installation trial.

1. Click **Report**.
2. Select the imported state, first result, and alternative result in that order.
3. Confirm that the numbered selections match your intended order.
4. Click **Create PDF**.
5. Download the PDF and source ZIP.

Check that the PDF includes the selected states, both figures, and recorded explanations. Report generation should not rerun the analysis or add analysis nodes.

Reports are retained under:

```text
projects/agent-demo-01/.saigen/reports/
```

## 8. Finish and keep the evidence

Press **Ctrl+C** in the terminal running the viewer to stop that test server.

Keep the complete `projects/agent-demo-01/` directory, including its hidden `.saigen/` directory. It contains the preserved files and history.

Record whether these checks passed:

| Check | Result |
| --- | --- |
| Installed CLI used outside the source checkout | |
| Skill used from project instructions without an explicit skill prompt | |
| Agent stopped at the requested inspection checkpoint | |
| First recorded analysis and figure appeared live | |
| Alternative branch preserved a visible command difference | |
| State previews and file links worked | |
| Selected-state PDF and source ZIP were correct | |

The automated checks already passed. Skill discovery and the quality of the fresh-agent experience still need this manual walkthrough.

## Use the same experience for biological data

In a workspace configured with actual VCF inputs, the first prompt could be:

> I want to analyze these variant calls. First, remove calls with read depth below 5 and show how many remain in each sample. Then we can decide whether to try a stricter threshold.

For raw FASTQ reads instead:

> I want to analyze these E. coli sequencing reads. First, check their quality and trim low-quality bases. Show me the QC results before we decide what to do next.

These are alternative examples, not actions to run on the synthetic count table. Configure that workspace's actual input paths and analysis project first. Scientific choices that remain ambiguous should be clarified; the recorder should not silently choose a different analysis.

Build logs, temporary environments, demo files, and reports stay outside the source repository.
