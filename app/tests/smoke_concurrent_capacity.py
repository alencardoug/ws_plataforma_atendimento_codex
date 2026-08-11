import os
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from customer_care.bootstrap import create_app

def run():
    client=TestClient(create_app())
    login=client.post('/api/v1/auth/operator/login',json={'email':os.environ['SMOKE_OPERATOR_EMAIL'],'password':os.environ['SMOKE_OPERATOR_PASSWORD']})
    assert login.status_code==200,login.text
    headers={'Authorization':f"Bearer {login.json()['access_token']}"}
    ids=[client.post('/api/v1/public/conversations').json()['conversation']['id'] for _ in range(6)]
    def claim(cid):
        with TestClient(create_app()) as concurrent_client:
            return concurrent_client.post(f'/api/v1/operator/conversations/{cid}/claim',headers=headers).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses=list(pool.map(claim,ids))
    active=client.get('/api/v1/operator/conversations?scope=active',headers=headers).json()
    assert statuses.count(200)==4,statuses
    assert statuses.count(409)==2,statuses
    assert len(active)==4,len(active)
    print({'concurrent_capacity':'ok','statuses':sorted(statuses),'active':len(active)})

if __name__=='__main__':
    run()
