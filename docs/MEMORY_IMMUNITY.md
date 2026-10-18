# ConvergeMind memory immunity model

ConvergeMind does not treat persistent memory as an unstructured transcript. Every durable assertion is a `MemoryClaim` with a lifecycle:

```text
proposed → verified → superseded
     └──→ quarantined
proposed ↔ disputed
```

## Graph model

```text
(Session)-[:ASSERTED]->(MemoryClaim)<-[:SUPPORTS]-(Evidence)
(Customer)-[:HAS_CLAIM]->(MemoryClaim)
(MemoryClaim)-[:CONTRADICTS|SUPERSEDES]->(MemoryClaim)
(Decision)-[:DEPENDS_ON]->(MemoryClaim)-[:CAPTURED_IN]->(HandoffCapsule)
(Session)-[:HANDED_OFF]->(HandoffCapsule)-[:DELIVERED_TO]->(Session)
```

`Evidence` carries the source type and trust score. Low-trust external evidence is quarantined before it reaches an agent context. A handoff capsule includes only verified claims, never a raw transcript.

## Revalidation query

When a verified claim replaces an earlier verified claim with the same key and a different value, ConvergeMind writes a `SUPERSEDES` edge and follows the old claim's dependencies:

```cypher
MATCH (current:MemoryClaim {id: $claim_id})-[:SUPERSEDES]->(old:MemoryClaim)
      <-[:DEPENDS_ON]-(decision:Decision)
SET decision.status = 'needs_revalidation'
RETURN decision.id, decision.text
```

The equivalent traversal marks old handoff capsules `needs_revalidation`. This is the core demonstration: a graph can show the operational consequences of changing context, instead of simply retrieving related text.
