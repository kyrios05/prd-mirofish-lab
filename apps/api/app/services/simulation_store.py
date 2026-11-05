"""Per-run state and streaming snapshots, owned by a chat session."""
from uuid import uuid4
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
import json
from app.services import state_db
from app.config import settings
from app.services.session_store import session_store


_runs = {}

def create_run(session, **values):
    run = {"run_id": uuid4().hex, "session_id": session.session_id, "status": "created", "simulation_events": [], **values}
    save_run(run)
    session.context["simulation_run_id"] = run["run_id"]
    session_store.save_session(session)
    return run


def save_run(run):
    _runs[(str(settings.state_db_path), run["run_id"])] = run
    state_db.save("run", run["run_id"], run)


def find_run(session, run_id="current"):
    key = session.context.get("simulation_run_id") if run_id == "current" else run_id
    cache_key = (str(settings.state_db_path), key)
    run = _runs.get(cache_key)
    if run is None:
        run = state_db.load("run", key) if key else None
        if run:
            for field in ("status", "report_status"):
                if run.get(field) == "streaming":
                    run[field] = "interrupted"
            _runs[cache_key] = run
    if not run or run["session_id"] != session.session_id:
        raise HTTPException(404, "Simulation run not found in this session")
    return run


async def resolve_run(request: Request):
    payload = await request.json() if request.method == "POST" else {}
    owner = request.query_params.get("session_id") or payload.get("session_id")
    session = session_store.get_session(owner) if owner else None
    if session is None:
        raise HTTPException(404, "A valid session_id is required")
    if request.url.path.endswith(("/setup", "/start")):
        values = {key: payload[key] for key in ("project_id", "graph_id", "stakeholder_personas") if key in payload}
        if request.url.path.endswith("/start") and not values.get("project_id"):
            try:
                previous = find_run(session)
            except HTTPException:
                previous = {}
            if previous.get("status") == "setup":
                values.update({key: previous.get(key) for key in ("project_id", "graph_id")})
        run = create_run(session, **values)
    else:
        run = find_run(session, request.query_params.get("run_id") or request.path_params.get("sim_id", "current"))
    try:
        yield run
    finally:
        save_run(run)


def stream_events(source, run, *, report=False):
    events_key = "report_events" if report else "simulation_events"
    status_key = "report_status" if report else "status"
    if run.get(status_key) == "completed":
        async def replay():
            for event in run.get(events_key, []):
                yield f"data: {json.dumps(event)}\n\n"
        return StreamingResponse(replay(), media_type="text/event-stream")
    if run.get(status_key) in {"streaming", "interrupted"}:
        raise HTTPException(409, "Run already started; retrieve saved results or start a new run")
    run[status_key] = "streaming"
    save_run(run)

    async def capture():
        try:
            async for raw in source:
                for line in raw.splitlines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    events = run.setdefault(events_key, [])
                    if not events or events[-1] != event:
                        events.append(event)
                    if event.get("type") in {"simulation_complete", "report_complete"}:
                        run[status_key] = "completed"
                    elif event.get("type") in {"simulation_error", "report_error"}:
                        run[status_key] = "failed"
                    if report and event.get("type") == "report_complete":
                        run["report_markdown"] = event["markdown"]
                    save_run(run)
                yield raw
        except Exception:
            run[status_key] = "failed"
            raise
        finally:
            if run.get(status_key) == "streaming":
                run[status_key] = "interrupted"
            save_run(run)
    return StreamingResponse(capture(), media_type="text/event-stream")
