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
`gpt-5.6-terra`), including its parallel simulation agents. The script rebuilds
the engine so local provider compatibility fixes are included, and reuses the
existing `mirofish-offline` Compose project and Neo4j volumes.

Graph embeddings still use the engine's configured `nomic-embed-text` model;
start the installed Ollama app before building graphs. Health checks alone do
not verify ontology generation, graph building, or simulation execution.

Open the app at <http://localhost:3000>. The engine backend is available at
<http://localhost:5001/health>.
