# Deploying the Doctus production agent (P4)

Target: **Vertex AI Agent Engine** (Google Cloud Agent Builder) hosting an
**ADK** agent whose tools are the deterministic Doctus clearance stack.

```
Gemini planner (ADK LlmAgent)
    └── doctus.cloud.tools.make_tools(CloudStudio)   ← the ONLY callable surface
          ├── generate_shot            Veo backend → sign C2PA → ingest
          ├── composite_shot           ingredient edges → sign C2PA → ingest
          ├── publish_video            ClearanceGate verdict-as-data
          ├── check_permission         preflight form of the gate
          └── propose_license_extension   deny → draft instrument (never signs)
```

The gate is deterministic code (D3): the model proposes, signed credentials
authorize. Deny explanations reach the model verbatim as tool results.

## 0. Prerequisites

```bash
gcloud auth login
gcloud config set project $GOOGLE_CLOUD_PROJECT
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com storage.googleapis.com
gsutil mb -l us-central1 gs://$GOOGLE_CLOUD_PROJECT-doctus-staging   # or: gcloud storage buckets create
```

Install local deps for deployment + cloud generation:

```bash
uv sync --group adk --group gcp
```

## 1. Smoke-test locally before deploying

```bash
.venv/Scripts/python.exe scripts/demo_arc_p4.py              # prebaked backend
DOCTUS_VEO_BACKEND=cloud .venv/Scripts/python.exe scripts/demo_arc_p4.py   # real Veo beat 1
adk web deploy/adk_app                                       # dev UI against the real agent
```

## 2. Deploy to Agent Engine

From the repo root:

```bash
adk deploy agent_engine \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=${GOOGLE_CLOUD_LOCATION:-us-central1} \
  --staging_bucket=gs://$GOOGLE_CLOUD_PROJECT-doctus-staging \
  --requirements_file=deploy/requirements.txt \
  deploy/adk_app
```

ADK packages `deploy/adk_app`, stages it to GCS, and creates a reasoningEngine
instance. Note the printed resource name
(`projects/<n>/locations/<r>/reasoningEngines/<id>`) - it is the deployment.

## 3. Verify the deployment

```python
import vertexai
vertexai.init(project=..., location=...)
from vertexai.preview.reasoning_engines import AdkApp
app = AdkApp(agent_engine="projects/.../reasoningEngines/<id>")
for event in app.stream_query(user_id="demo", message="Produce one hero shot,
publish it to festival/US, then try trailer/US"):
    print(event)
```

Expected behavior on camera (the demo arc, beats 1–6): shot created +
ingested trusted; festival publish ALLOWED; trailer publish DENIED with
`SCOPE_EXCEEDED`; the agent drafts the license extension and reports that only
a human can approve it (`countersign` ledger / approval UI).

## 4. IAM scoping — least privilege

See [iam.md](iam.md). Summary: one dedicated service account
(`doctus-agent-engine`) runs the deployment; it gets Vertex AI user + storage
object admin on the staging bucket only. Human approvers interact through the
countersign seam; no agent identity can approve instruments.
