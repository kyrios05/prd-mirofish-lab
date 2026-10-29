import pytest

from app.schemas import PRDDocument
from app.services.mirofish_service import MiroFishService


async def test_failed_graph_build_does_not_return_an_invented_graph_id(monkeypatch, full_prd):
    service = MiroFishService()
    calls = []

    async def request(method, path, **kwargs):
        calls.append(path)
        if path == "/graph/ontology/generate":
            return {"data": {"project_id": "proj-real"}}
        if path == "/graph/build":
            return {"data": {"task_id": "task-failed"}}
        pytest.fail(f"Unexpected recovery call: {path}")

    async def failed_task(task_id):
        raise RuntimeError("Neo4j graph build failed")

    monkeypatch.setattr(service, "_request", request)
    monkeypatch.setattr(service, "_wait_for_task", failed_task)
    prd = PRDDocument(**full_prd)

    with pytest.raises(RuntimeError, match="Neo4j graph build failed"):
        await service.setup_project_and_graph(prd)
    assert calls == ["/graph/ontology/generate", "/graph/build"]


async def test_engine_progress_and_completion_use_browser_units(monkeypatch):
    service = MiroFishService()

    async def request(*args, **kwargs):
        return {"data": {
            "runner_status": "completed",
            "progress_percent": 100,
            "all_actions": [{"agent_name": "검토자", "action_args": {"content": "검증 완료"}}],
        }}

    monkeypatch.setattr(service, "_request", request)
    events = [event async for event in service.poll_events("sim-real")]
    assert [event["type"] for event in events] == ["agent_post", "simulation_complete"]
    assert all(event["progress"] == 1.0 for event in events)


@pytest.mark.parametrize("status", ["failed", "stopped"])
async def test_engine_failure_emits_a_terminal_error(monkeypatch, status):
    service = MiroFishService()

    async def request(*args, **kwargs):
        return {"data": {
            "runner_status": status,
            "progress_percent": 25,
            "all_actions": [],
            "error": "Engine process terminated",
        }}

    monkeypatch.setattr(service, "_request", request)
    events = [event async for event in service.poll_events("sim-real")]
    assert len(events) == 1
    assert events[0]["type"] == "simulation_error"
    assert events[0]["content"] == "Engine process terminated"
    assert events[0]["progress"] == 0.25
