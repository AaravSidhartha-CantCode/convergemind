# ConvergeMind demo recording (2–3 minutes)

Use fabricated seed data only. The hosted/demo API has no authentication, so do not enter real customer information.

## Before recording

1. Start FalkorDB and the app using the README setup steps.
2. Run `python -m backend.seed_data` and open the app at `http://localhost:8501`.
3. Select `cust_bob`. Confirm the graph and seeded history are visible.
4. Have the FalkorDB Browser at `http://localhost:3000` ready if you want a brief database view.

## Run of show

**0:00–0:20 — The problem.** Show the two separate support panels and the Memory Guardian panel. Say: “A chat support agent and an email support agent start with separate context windows. If the customer switches channels, the second agent needs memory without receiving the first agent’s transcript. A third agent governs whether that memory is safe to reuse.”

**0:20–1:00 — Recall from graph memory.** In ChatAgent, send: `I'm locked out of my account again.` Point to the visible tool trace and changing customer graph. Explain that the agent recalls Bob’s prior SMS delivery issue and checks the shared procedural memory for a resolution.

**1:00–1:40 — Handoff.** Use **hand off chat to email**, then ask EmailAgent: `What did we learn about this lockout, and what should I do?` Show that EmailAgent reads the session/facts from FalkorDB and responds without a transcript being passed between agents.

**1:40–2:10 — Govern a memory.** Click **simulate untrusted memory** and show that it is quarantined. Then click **simulate verified change**, ask MemoryGuardian to audit the tenant, and verify the proposed carrier update. Point out the affected decision marked **REVALIDATE**. Explain that the Guardian uses separate FalkorDB tools and cannot call customer-support tools.

**2:10–2:30 — Show the graph and close.** Point out the customer’s session/fact history and the separate shared resolution graph in the UI. If time permits, show the corresponding graph key in FalkorDB Browser. State that the demo uses synthetic data, FalkorDB stores the persistent graph memory, and the project is entered in Track 2: Agent Memory and Coordination. Describe tenant boundaries accurately: graph keys separate stored graphs and model tools are bound to the selected request, while the demo HTTP API does not implement user authentication.

## Recording checklist

- Keep the browser address bar and app name visible at the opening.
- Make sure tool traces and graph changes are readable in the capture.
- Avoid showing API keys, environment files, or account dashboards.
- Rewatch the exported video and confirm its share link works in a signed-out/private browser before adding it to the submission.
