# prd-mirofish-lab
PRD-MiroFish-Lab is a chat-driven PRD generation and validation system that converts product conversations into structured PRDs and validates them through MiroFish-based simulation workflows.

## Run the MiroFish engine

Keep the `MiroFish-Offline` checkout next to this repository, then run:

```sh
bash scripts/mirofish-up.sh
docker compose up -d --build api web
```

Set `MIROFISH_SOURCE_DIR` if the engine checkout is elsewhere. The engine uses
`OPENAI_API_KEY` and `OPENAI_MODEL` from `apps/api/.env` (default model:
`gpt-6.1-terra`, reasoning effort `high`), including its parallel simulation agents. The script rebuilds
the engine so local provider compatibility fixes are included, and reuses the
existing `mirofish-offline` Compose project and Neo4j volumes.

Graph embeddings still use the engine's configured `nomic-embed-text` model;
start the installed Ollama app before building graphs. Health checks alone do
not verify ontology generation, graph building, or simulation execution.
OASIS also downloads its Twitter recommendation model on first use; the
Compose override persists its Hugging Face cache across engine recreation.

Open the app at <http://localhost:3000>. The engine backend is available at
<http://localhost:5001/health>.


### Saved sessions and simulation results

The single-worker lab API stores conversation, PRD, checkpoints, and per-run
simulation/report snapshots in `STATE_DB_PATH` (default `data/state.sqlite3`).
Docker Compose preserves this directory in the `prd_state` named volume.
Back up this database alongside the engine's data. Each browser tab remembers
its session ID in sessionStorage, so reloading resumes that session.

Simulation stream/result/report endpoints require `session_id`. The run ID is
returned by `/simulation/start`; `current` resolves only inside that session.
Completed streams replay stored events without repeating model calls. An
interrupted simulation keeps its partial results; start a new run to retry.
Report failures stay in the generating phase with an explicit retry button.

`GET /health` checks process liveness. `GET /ready` returns 503 when local
storage, required LLM configuration, or the enabled MiroFish dependency is
unavailable. Readiness checks do not perform billable LLM requests.


### PRD Lab Nemotron Reality Seeds

Reality Seeds offers an opt-in **Nemotron Korean users + expert reviewers**
source in Live mode. This app owns `POST /simulation/reality-seeds/nemotron`
(`session_id`, `prd`) and `GET /simulation/reality-seeds/{selection_id}?session_id=...`.
It does not call or change MiroFish-Offline's `/api/persona-lab` endpoints.
The existing PRD-only and Mock generation paths remain available.

The dedicated service fetches 64 candidates from eight separated windows of
NVIDIA's `nvidia/Nemotron-Personas-Korea` train split, then uses the configured
OpenAI model (`gpt-6.1-terra`, high) to select/adapt eight relevant users/field
workers and generate four expert reviewers. This is selection from a candidate
sample, not an exhaustive search or a representative customer survey.

Each saved selection retains original rows, the exact candidate snapshot/hash,
observed Hub revision, UUID-to-member mapping, generated review hypotheses,
license/attribution, and PRD fingerprint. The viewer API serves its current
export, so the observed Hub revision is not a revision pin. Stored source
snapshots are the reproducible evidence. Source metadata stays outside
`PRD_SCHEMA.json` Stakeholder objects. Runs keep both the generated panel and
the final manually edited members with their source references. A changed PRD
requires generating a new selection. Failures return an error; there is no
silent replacement with Mock or another project's personas.

Dataset: https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea
Attribution: NVIDIA Nemotron-Personas-Korea, CC BY 4.0. All source personas are
synthetic; this dataset covers adults and does not establish actual customer
preferences or product demand.
