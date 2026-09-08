# IAM scoping for the Doctus deployment (P4)

Principle: the agent's service account can **produce and ask**, never
**authorize**. Human countersignature (CONTEXT.md invariant 6) is a separate
identity boundary, not a role the deployment holds.

## Service accounts

| Identity | Role/binding | Scope |
|---|---|---|
| `doctus-agent-engine` (runs the Agent Engine instance) | `roles/aiplatform.user` | project (Vertex AI: Veo generate, Agent Engine serve) |
| 〃 | `roles/storage.objectAdmin` | staging bucket **only** (`gs://…-doctus-staging`) |
| 〃 | — nothing else — | no countersign authority, no IAM mutation, no secret accessor |
| human studio lead | approves via countersign seam (UI / `scripts/countersign.py`) | outside GCP IAM entirely in v1 |

## Bootstrap

```bash
gcloud iam service-accounts create doctus-agent-engine \
  --display-name="Doctus production agent (Agent Engine)"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:doctus-agent-engine@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud storage buckets add-iam-policy-binding \
  gs://$GOOGLE_CLOUD_PROJECT-doctus-staging \
  --member="serviceAccount:doctus-agent-engine@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Deploy AS that identity:
gcloud deploy --project=$GOOGLE_CLOUD_PROJECT ...   # or set agent_engine.create with service_account=
```

## Why this shape

- **Veo + Agent Engine need Vertex AI user.** That is the entire cloud
  footprint of the deterministic core; everything else is local.
- **Staging bucket is object-scoped.** The deployment stages code there;
  nothing else in the product uses GCS.
- **Authorization is not an IAM question here.** Rights live in signed C2PA
  claims inside the rights graph; the gate reads them deterministically. A
  compromised agent identity can generate shots and receive DENYs - it cannot
  mint rights, because approval writes require a human actor at the
  countersign seam and the negotiator refuses to self-sign (D3/D5/invariant 6).
