import json
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.schemas import RealitySeedRequest
from app.services import reality_seeds, state_db
from app.services.session_store import session_store
from app.services.simulation_store import find_run


def rows_and_panel():
    rows = [{'uuid':f'uuid-{i}', 'age':30+i, 'occupation':'사무직', 'persona':f'합성 인물 {i}'} for i in range(64)]
    panel = {'notice': 'Synthetic test participants', 'members':[{'source_uuid':f'uuid-{i}' if i<8 else None, 'name':f'검토자{i}', 'role':'사용자' if i<8 else '전문가', 'review_angle':'원본 배경: 사무직. 제품 검토 가설: 편의성 검토', 'likely_objections':['가입 절차가 복잡함']} for i in range(12)]}
    return rows, panel


def configure(monkeypatch, panel=None):
    rows, default_panel = rows_and_panel()
    monkeypatch.setattr(settings, 'ollama_enabled', True)
    monkeypatch.setattr(settings, 'llm_provider', 'openai')
    monkeypatch.setattr(reality_seeds, 'fetch_candidates', AsyncMock(return_value=(rows, {'dataset':reality_seeds.DATASET,'license':'CC-BY-4.0'})))
    service = type('LLM', (), {'chat': AsyncMock(return_value=json.dumps(panel or default_panel))})()
    monkeypatch.setattr(reality_seeds, 'get_llm_service', lambda:service)
    return service


def test_dedicated_selection_preserves_sources_outside_prd_and_is_owned(monkeypatch):
    configure(monkeypatch)
    a,b=session_store.create_session(), session_store.create_session()
    client=TestClient(app)
    prd={'product':{'name':'직장인 점심 앱'}}
    response=client.post('/simulation/reality-seeds/nemotron',json={'session_id':a.session_id,'prd':prd})
    assert response.status_code==200
    data=response.json()
    assert len(data['stakeholders'])==12
    assert all('source_uuid' not in member for member in data['stakeholders'])
    selection=client.get(f'/simulation/reality-seeds/{data["selection_id"]}',params={'session_id':a.session_id}).json()
    assert len(selection['original_rows'])==8
    assert selection['original_rows'][0]['age']==30
    assert len(selection['candidate_snapshot'])==64
    assert a.current_prd_draft is None
    assert client.get(f'/simulation/reality-seeds/{data["selection_id"]}',params={'session_id':b.session_id}).status_code==404


@pytest.mark.parametrize('kind',['unknown','duplicate','too_few'])
async def test_invalid_model_sources_are_rejected(monkeypatch,kind):
    rows,panel=rows_and_panel()
    if kind=='unknown':panel['members'][0]['source_uuid']='invented'
    if kind=='duplicate':panel['members'][0]['source_uuid']='uuid-1'
    if kind=='too_few':panel['members'].pop()
    configure(monkeypatch,panel)
    with pytest.raises(ValueError):
        await reality_seeds.generate_selection(RealitySeedRequest(session_id='test',prd={'product':{'name':'test'}}))


def test_failure_never_uses_other_project_or_mock(monkeypatch):
    service=configure(monkeypatch)
    service.chat.side_effect=RuntimeError('upstream failure')
    owner=session_store.create_session()
    response=TestClient(app).post('/simulation/reality-seeds/nemotron',json={'session_id':owner.session_id,'prd':{'product':{'name':'test'}}})
    assert response.status_code==502
    assert 'stakeholders' not in response.json()


def test_selection_links_to_run_and_retains_manual_edits(monkeypatch):
    configure(monkeypatch)
    owner=session_store.create_session()
    owner.current_prd_draft={'product':{'name':'앱'}}
    session_store.save_session(owner)
    client=TestClient(app)
    data=client.post('/simulation/reality-seeds/nemotron',json={'session_id':owner.session_id,'prd':owner.current_prd_draft}).json()
    final=data['stakeholders'];final[0]['review_angle']='사용자가 수정한 관점'
    response=client.post('/chat/action',json={'session_id':owner.session_id,'action_id':'start_simulation','payload':{'live':False,'seed_selection_id':data['selection_id'],'stakeholder_personas':final,'stakeholder_seed_refs':[m['source_uuid'] for m in data['members']]}})
    assert response.status_code==200
    run=find_run(owner)
    assert run['seed_selection_id']==data['selection_id']
    assert run['seed_final_members'][0]['stakeholder']['review_angle']=='사용자가 수정한 관점'
    assert run['seed_adapted_members'][0]['review_angle']!=run['seed_final_members'][0]['stakeholder']['review_angle']
    owner.current_prd_draft={'product':{'name':'다른 앱'}}
    session_store.save_session(owner)
    response=client.post('/chat/action',json={'session_id':owner.session_id,'action_id':'start_simulation','payload':{'seed_selection_id':data['selection_id']}})
    assert response.status_code==409


async def test_dataset_transport_retries_and_preserves_exact_snapshot(monkeypatch):
    import httpx
    import respx
    async def no_sleep(_): pass
    monkeypatch.setattr(reality_seeds.asyncio,'sleep',no_sleep)
    requests=[]
    def respond(request):
        offset=int(request.url.params['offset']);length=int(request.url.params['length'])
        requests.append((offset,length))
        if len(requests)==1:
            return httpx.Response(502)
        rows=[{'row':{'uuid':f'row-{i}','age':25,'occupation':'사용자'},'truncated_cells':[]} for i in range(offset,offset+length)]
        return httpx.Response(200,json={'num_rows_total':1000,'rows':rows})
    with respx.mock() as mock:
        mock.get(f'https://huggingface.co/api/datasets/{reality_seeds.DATASET}').respond(200,json={'sha':'observed-revision'})
        mock.get('https://datasets-server.huggingface.co/rows').mock(side_effect=respond)
        rows,meta=await reality_seeds.fetch_candidates({'product':{'name':'test'}})
    assert len(rows)==64
    assert len({row['uuid'] for row in rows})==64
    assert meta['candidate_snapshot_sha256']==reality_seeds.fingerprint(rows)
    assert meta['upstream_revision_observed']=='observed-revision'
    assert requests[0]==requests[1]  # bounded retry, same requested data


def test_mock_configuration_and_missing_session_do_not_call_dataset(monkeypatch):
    service=configure(monkeypatch)
    client=TestClient(app)
    assert client.post('/simulation/reality-seeds/nemotron',json={'session_id':'missing','prd':{}}).status_code==404
    monkeypatch.setattr(settings,'ollama_enabled',False)
    owner=session_store.create_session()
    assert client.post('/simulation/reality-seeds/nemotron',json={'session_id':owner.session_id,'prd':{}}).status_code==409
    service.chat.assert_not_awaited()
