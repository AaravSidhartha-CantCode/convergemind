# Submission details to fill in

The repository and complete local setup are ready. These two public URLs can only be created from accounts you control.

| Hackathon field | What to paste | How to get it |
|---|---|---|
| Repository | `https://github.com/AaravSidhartha-CantCode/convergemind` | Already public. |
| Track | `Track 2: Agent Memory and Coordination` | Select it in the form. |
| Live demo URL | `https://<your-railway-service>.up.railway.app` | Follow [`DEPLOY.md`](../DEPLOY.md): create a FalkorDB Cloud instance, seed it, deploy the repository to Railway, then generate a public domain. |
| Demo video URL | Your unlisted YouTube, Loom, or Drive share URL | Record the 2–3 minute flow in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md), upload it, then verify the link in a private browser window. |

## Credentials needed for deployment

Set these only in Railway's environment-variable dashboard. Do not commit them to `.env`, the README, a video, or a submission form.

- `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_PASSWORD` from FalkorDB Cloud
- `GROQ_API_KEY` from the Groq console
- Optional: `GROQ_MODEL` to choose a tool-calling Groq model

The deployed project is a public synthetic-data demo. It does not include end-user authentication, so do not load real customer data into it.
