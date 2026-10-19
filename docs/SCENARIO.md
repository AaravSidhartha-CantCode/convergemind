# Why the demo uses housing recovery

## The user problem

After a flood or displacement event, a household may speak to several coordinators while dealing with a lost phone, unstable internet access, missing documents, and accessibility needs. Asking them to repeat those details at every channel switch is exhausting. Using stale contact information or an unverified referral can be harmful.

## The product boundary

ConvergeMind helps a caseworker **remember and review** coordination context. It does not make eligibility decisions, contact providers, send messages, or replace human casework. All people, cases, providers, and playbooks in the demo are fabricated.

## Why FalkorDB is necessary

Each household has an isolated graph containing sessions, facts, claims, evidence, recommendations, and handoff capsules. The team playbook graph is shared deliberately. A new coordinator can traverse the case context without receiving a transcript, while Memory Safety Review can follow `SUPERSEDES` and `DEPENDS_ON` relationships to identify recommendations that need revalidation.

This is the Track 2 argument in one workflow: persistent episodic, semantic, and procedural memory; state shared across independent agents; and separate graph memory for every case.

## Why no live email or SMS integration

The core product claim is safe graph-backed coordination, not message delivery. A live email or SMS integration would add credentials, provider dependencies, and a risk of sending a real message without proving the memory system. The UI uses separate intake and follow-up agent sessions to demonstrate the exact memory and handoff boundary the product needs.
