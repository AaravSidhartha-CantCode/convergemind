# Deploying ConvergeMind

Use Railway for the public app. Attach either a Railway-hosted FalkorDB service or a FalkorDB Cloud instance.

The container runs both processes (uvicorn on loopback, Streamlit on the public port), so judges get one URL with no CORS setup.

> **Demo security boundary:** the API has no authentication and accepts a caller-selected `customer_id`. Deploy only with the fabricated seed data; anyone with the public URL can inspect the demo tenants. FalkorDB graph keys isolate graph queries, but this demo does not authenticate users or authorize tenant access.

---

## Option A: FalkorDB Cloud

1. Sign up at <https://app.falkordb.cloud> and create a free instance.
2. From the instance page, copy the **host**, **port** and **password**.

Sanity-check it from your machine before going further, so a bad credential fails here rather than inside a deploy log:

```bash
FALKORDB_HOST=<host> FALKORDB_PORT=<port> FALKORDB_PASSWORD=<password> \
  python -c "from backend.db import get_shared_graph; print(get_shared_graph().query('RETURN 1').result_set)"
```

Expect `[[1]]`.

On Windows PowerShell, set the same values for the current terminal like this:

```powershell
$env:FALKORDB_HOST = "<host>"
$env:FALKORDB_PORT = "<port>"
$env:FALKORDB_PASSWORD = "<password>"
py -3 -c "from backend.db import get_shared_graph; print(get_shared_graph().query('RETURN 1').result_set)"
```

### Seed the Cloud instance

Run once, against the cloud credentials, so judges land on populated graphs rather than an empty demo:

```bash
FALKORDB_HOST=<host> FALKORDB_PORT=<port> FALKORDB_PASSWORD=<password> \
  python -m backend.seed_data
```

Expect `Seeded 4 synthetic customers`.

If you used the PowerShell variables above, run `py -3 -m backend.seed_data` in the same terminal.

## Option B: FalkorDB as a private Railway service

1. In the same Railway project, create a new service from the image `falkordb/falkordb:4.22.1`.
2. Name it `falkordb`. Do not generate a public domain for it.
3. In the ConvergeMind app service, set `FALKORDB_HOST=falkordb.railway.internal` and `FALKORDB_PORT=6379`. Leave `FALKORDB_PASSWORD` unset unless you explicitly configured one for the database service.
4. Seed the graphs from a Railway shell for the **app** service with `python -m backend.seed_data`. Run it once after the database is reachable.

This removes the need for a FalkorDB Cloud account and keeps the database on Railway's private network.

## Deploy the app service to Railway

```bash
npm i -g @railway/cli
railway login
railway init          # from the repo root
railway up
```

Then set the environment variables. For Cloud, use the host, port, and password copied above. For the private Railway service, use the variables in Option B.

```bash
railway variables set GROQ_API_KEY=<your groq key>
railway variables set GROQ_MODEL=openai/gpt-oss-120b
```

Do **not** set `API_BASE_URL`; the Dockerfile already points it at the in-container backend, and overriding it will break the UI.

Generate a public domain under Settings, Networking, Generate Domain.

## Smoke test

Open the public Railway domain in a browser. The public port serves Streamlit, while the FastAPI process intentionally listens only on the container loopback interface; `/health` on the public URL is therefore not an API health check.

Pick `cust_maya` and send ChatAgent *"I lost my phone in the flood. What is the safe next step for my housing case?"* A working deployment recalls Maya's no-SMS constraint, finds the `temporary_housing` playbook, and writes the resulting recommendation back to the graph. Also use **add verified carrier update**, then ask MemoryGuardian to audit the case.

## Put the URL in the README

Replace the deployment line in `README.md` with the live domain before submitting, since the submission checklist asks for it explicitly.

---

## If it fails

| Symptom | Cause |
|---|---|
| UI loads, "Backend unreachable" | uvicorn died inside the container. Check Railway logs; usually a missing `FALKORDB_*` variable. |
| "No tenants yet" | Step 2 was skipped or ran against local rather than cloud. |
| Agent replies but calls no tools | `GROQ_MODEL` points at a model without tool support. Check `python -c "from groq import Groq; import os; print([m.id for m in Groq(api_key=os.environ['GROQ_API_KEY']).models.list().data])"`. |
| 429 from Groq | Free-tier rate limit. It resets quickly; relevant only if several judges test at once. |

## Cost

Free on both tiers for a hackathon's traffic. Railway's starter credit covers a single always-on container for the judging window; FalkorDB Cloud's free instance is well above what four synthetic customers need.
