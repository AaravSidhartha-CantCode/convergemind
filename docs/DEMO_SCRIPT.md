# ConvergeMind recording script (2 minutes 30 seconds)

ConvergeMind is a governed memory layer for multi-agent systems. The support case is synthetic example data used to make the mechanics visible. The agents do not send email or change an account.

## Prepare the screen

1. In the Railway **app service**, deploy the latest `main` branch.
2. Open the app service **Shell** and run `python -m scripts.reset_demo`.
3. Open the public app URL at normal browser zoom. Select `cust_bob` from **demo tenant**.
4. Keep the page at the top. Do not show Railway, FalkorDB Browser, API keys, or environment variables.

## Exact recording sequence

### 0:00–0:15 — State the product

Show the header, Bob's three-card case summary, the two agent channels, and Memory Safety Review.

Say: “ConvergeMind is a governed memory layer for teams of AI agents. The support case is only a demo workload. The product is what happens when an agent learns a fact, another agent needs it later, and then that fact changes.”

### 0:15–0:45 — Prove persistent and shared memory

1. Under **chat channel**, click **load suggested case question**.
2. The text box fills with: `I'm locked out of my account again. What should I do?`
3. Click **send**.
4. Pause on the reply and the visible tool trace.

Say: “This chat agent starts with no transcript. Its first tool call is `recall_customer_context`, which retrieves Bob's no-SMS constraint from his private FalkorDB graph. It then looks up the shared password-reset playbook and records the recommended resolution.”

### 0:45–1:10 — Prove handoff without a transcript

1. Click **hand off chat to email** below the email channel.
2. Under **email channel**, click **load suggested case question**.
3. Replace the text with: `What do we know about Bob's lockout, and what should happen next?`
4. Click **send**.

Say: “Email is a separate agent session. No transcript was copied. It reads the same tenant graph, so it knows the customer constraint and previous recommendation immediately.”

### 1:10–1:50 — Prove the winning feature: memory change management

1. In **memory safety review**, click **add verified carrier update**.
2. A proposed `known_blocker` claim appears. Point to its evidence and trust score.
3. Click **verify** beneath that claim. Do not use the audit-chat box for the recording; the direct button makes the result deterministic.
4. Pause on the **REVALIDATE** alert.

Say: “This is the difference between stored context and governed memory. New evidence does not silently overwrite an old fact. It becomes a claim with provenance and trust. When verified, ConvergeMind follows the graph to find every earlier decision that depended on the old claim and marks it for revalidation.”

### 1:50–2:15 — Show the proof graph

1. Scroll to **CASE EVIDENCE — Why this recommendation is trusted**.
2. Point to the left-to-right graph. Hover the `known_blocker` claim if the label is small.
3. Point to the `SUPERSEDES` and `DEPENDS_ON` relationship labels, then to the **Reusable playbooks** panel beside it.

Say: “FalkorDB is doing the work here. Each tenant gets an isolated graph for private episodic and semantic memory. Reusable procedures live in a separate shared graph. The relationship path explains exactly why an earlier decision is now stale.”

### 2:15–2:30 — Close

Say: “Remove FalkorDB and the agents lose their durable memory, safe handoffs, evidence lineage, and blast-radius analysis. That is ConvergeMind: version control and observability for agent memory.”

## Do not add live email or SMS for this submission

The hackathon asks for graph-backed agent memory and coordination, not a messaging integration. Connecting Gmail, Twilio, or an SMTP provider would add credentials, personal-data risk, and delivery failures without proving the graph memory system. For a later production version, channels would ingest authenticated messages into a tenant graph and require human approval before external delivery.
