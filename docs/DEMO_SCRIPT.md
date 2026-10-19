# ConvergeMind demo recording (2–3 minutes)

Use fabricated seed data only. ConvergeMind demonstrates coordination for a housing-recovery team after a flood; it does not contact relief providers, send messages, decide eligibility, or provide emergency, legal, or medical advice.

## Before recording

1. Start FalkorDB and the app using the README setup steps.
2. Run `python -m scripts.reset_demo` and open the app at `http://localhost:8501`.
3. Select `cust_maya`. Confirm Maya's case brief, graph, and prior temporary-housing playbook are visible.

## Run of show

**0:00–0:20 — The human problem.** Show Maya's case brief. Say: “After displacement, people often repeat safe contact details, document status, and accessibility needs every time a case changes hands. A forgotten detail can make a recommendation unsafe or force someone to start again.”

**0:20–0:55 — Intake remembers.** In **Intake Chat**, use the suggested question or send: `I lost my phone in the flood. What is the safe next step for my housing case?` Point to the tool trace. Explain that the agent starts with an empty context window, then reads Maya's isolated FalkorDB graph: her no-SMS constraint, step-free housing need, document status, and a prior temporary-housing playbook.

**0:55–1:20 — The handoff does not lose Maya's story.** Click **hand off chat to email**. In **Case Follow-up**, send: `What do we know about Maya's case, and what should a caseworker review next?` Explain that this is a separate agent session with no transcript; it reads the same graph.

**1:20–1:55 — New information is governed.** Click **add verified carrier update**. The new contact claim is proposed rather than silently trusted. Use the suggested evidence-review prompt in **Memory Safety Review**, then verify the claim. Point to the earlier recommendations marked **REVALIDATE** and the graph edge showing the old contact constraint was superseded.

**1:55–2:15 — Close.** Say: “ConvergeMind gives housing-recovery teams persistent, shared, and governed case memory. FalkorDB stores the private case graph, reusable team playbooks, and the evidence path behind every recommendation.”

## Recording checklist

- Keep the case brief, tool traces, and Memory Safety Review visible.
- Describe every person and case as synthetic.
- Do not show deployment dashboards, API keys, or environment variables.
- Describe the scope accurately: this is a coordination and recommendation demo, not a provider-messaging or eligibility system.
