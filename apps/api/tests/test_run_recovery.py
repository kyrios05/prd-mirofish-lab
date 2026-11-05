import json
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routes import simulation
from app.services.session_store import SessionStore, session_store
from app.services.simulation_store import create_run, find_run, save_run, stream_events
from app.services import simulation_store


def test_new_run_uses_requested_ids_and_has_no_previous_report(monkeypatch):
    monkeypatch.setattr(simulation.settings, 'mirofish_mode', 'live')
    engine = AsyncMock(return_value='engine-B')
    monkeypatch.setattr(simulation.mirofish, 'create_and_start_simulation', engine)
    session = session_store.create_session()
    previous = create_run(session, project_id='A', graph_id='graph-A', report_task_id='old-report')
    client = TestClient(app)
    response = client.post('/simulation/start', json={'session_id': session.session_id, 'live': True, 'project_id': 'B', 'graph_id': 'graph-B'})
    assert response.status_code == 200
    engine.assert_awaited_once_with('B', 'graph-B')
    current = find_run(session)
    assert current['run_id'] != previous['run_id']
    assert 'report_task_id' not in current


def test_session_and_run_recover_from_disk():
    session = session_store.create_session()
    session.current_prd_draft = {'product': {'name': 'recover me'}}
    session.add_turn('hello', 'welcome')
    run = create_run(session, mode='mock', status='completed', report_markdown='saved report')
    restored = SessionStore().get_session(session.session_id)
    assert restored.current_prd_draft == session.current_prd_draft
    assert restored.conversation_history[0].content == 'hello'
    simulation_store._runs.clear()
    assert find_run(restored)['report_markdown'] == 'saved report'
    assert find_run(restored)['run_id'] == run['run_id']


def test_result_requires_owning_session_and_returns_saved_events():
    a, b = session_store.create_session(), session_store.create_session()
    run = create_run(a, status='completed', simulation_events=[{'type': 'agent_post', 'content': 'A only'}])
    client = TestClient(app)
    url = f'/simulation/{run["run_id"]}/result'
    assert client.get(url).status_code == 404
    assert client.get(url, params={'session_id': b.session_id}).status_code == 404
    assert client.get(url, params={'session_id': a.session_id}).json()['logs'][0]['content'] == 'A only'
    assert client.get('/simulation/missing/result', params={'session_id': a.session_id}).status_code == 404


async def test_interleaved_streams_keep_results_and_replay_without_rerunning():
    a, b = session_store.create_session(), session_store.create_session()
    runs = [create_run(a), create_run(b)]
    calls = []
    async def events(name):
        calls.append(name)
        yield f'data: {json.dumps({"type": "agent_post", "content": name})}\n\n'
        yield 'data: {"type":"simulation_complete"}\n\n'
    streams = [stream_events(events(name), run) for name, run in zip(['A','B'],runs)]
    await anext(streams[0].body_iterator)
    await anext(streams[1].body_iterator)
    for stream in streams:
        async for _ in stream.body_iterator:
            pass
    for name, run in zip(['A','B'],runs):
        assert run['simulation_events'][0]['content'] == name
        replay = stream_events(events('must not run'),run)
        async for _ in replay.body_iterator:
            pass
    assert calls == ['A','B']


async def test_report_failure_stays_failed_and_cannot_complete_chat(monkeypatch):
    async def fail():
        yield 'data: {"type":"report_error","markdown":"failed"}\n\n'
    owner = session_store.create_session()
    run = create_run(owner)
    response = stream_events(fail(), run, report=True)
    async for _ in response.body_iterator:
        pass
    assert run['report_status'] == 'failed'
    response = TestClient(app).post('/chat/action', json={'session_id':owner.session_id,'action_id':'generate_report_complete'})
    assert response.status_code == 409


def test_failed_report_with_100_percent_never_completes(monkeypatch):
    async def no_sleep(_): pass
    monkeypatch.setattr(simulation.asyncio, 'sleep', no_sleep)
    status = AsyncMock(return_value={'data': {'status': 'failed', 'progress': 100, 'error': 'upstream failure'}})
    monkeypatch.setattr(simulation.mirofish, 'get_report_status', status)
    owner = session_store.create_session()
    run = create_run(owner, mode='live', simulation_id='engine', report_task_id='task-B')
    response = TestClient(app).get('/simulation/current/report/stream', params={'session_id':owner.session_id})
    assert 'report_error' in response.text
    assert 'report_complete' not in response.text
    status.assert_awaited_once_with(task_id='task-B')


def test_health_and_readiness_are_distinct(monkeypatch):
    monkeypatch.setattr(simulation.settings, 'mirofish_mode', 'live')
    import httpx
    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx.AsyncClient, 'get', unavailable)
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    ready = client.get('/ready')
    assert ready.status_code == 503
    assert ready.json()['checks']['mirofish'] is False


def test_exact_report_is_loaded_from_completed_task(monkeypatch):
    async def no_sleep(_): pass
    monkeypatch.setattr(simulation.asyncio, 'sleep', no_sleep)
    monkeypatch.setattr(simulation.mirofish, 'get_report_status', AsyncMock(return_value={'data': {'status':'completed','result':{'report_id':'new-report'}}}))
    exact = AsyncMock(return_value={'data':{'markdown_content':'# New report'}})
    monkeypatch.setattr(simulation.mirofish, 'get_report', exact)
    owner = session_store.create_session()
    create_run(owner, mode='live', simulation_id='engine', report_task_id='new-task')
    response = TestClient(app).get('/simulation/current/report/stream', params={'session_id':owner.session_id})
    assert '# New report' in response.text
    exact.assert_awaited_once_with('new-report')
    assert find_run(owner)['report_status'] == 'completed'


async def test_disconnect_keeps_partial_results_and_requires_explicit_new_run():
    from fastapi import HTTPException
    async def events():
        yield 'data: {"type":"agent_post","content":"partial"}\n\n'
        yield 'data: {"type":"simulation_complete"}\n\n'
    owner = session_store.create_session()
    run = create_run(owner)
    response = stream_events(events(), run)
    await anext(response.body_iterator)
    await response.body_iterator.aclose()
    assert run['status'] == 'interrupted'
    assert run['simulation_events'][0]['content'] == 'partial'
    with pytest.raises(HTTPException) as exc:
        stream_events(events(), run)
    assert exc.value.status_code == 409


def test_direct_mock_start_does_not_require_a_previous_run():
    owner = session_store.create_session()
    response = TestClient(app).post('/simulation/start', json={'session_id':owner.session_id,'live':False})
    assert response.status_code == 200
    assert response.json()['simulation_id'] == find_run(owner)['run_id']
