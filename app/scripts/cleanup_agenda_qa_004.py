"""specs/004-dynamic-appointment-availability/tasks.md T070: soft-
deactivates the `agenda` Q&A entries that describe booking/hold/identity/
payment-confirmation behavior this feature does not implement (spec.md §5
item 3 — QA-016/017/021/022/023/024; QA-017 added to that original
human-identified set of 5 during this re-evaluation, since it claims
professional-name filtering the resolver has no keyword for). Via the
real DELETE /operator/knowledge/qa/{qa_id} endpoint (V2-8 CRUD, is_active
= false, never a hard delete) — same audited path an operator would use.
Run manually:

    PYTHONPATH=. SMOKE_OPERATOR_EMAIL=... SMOKE_OPERATOR_PASSWORD=... \\
        python scripts/cleanup_agenda_qa_004.py
"""

import os

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app

DEACTIVATE_QA_IDS = [
    "QA-016",  # "A agenda exibida fica reservada para mim?" — hold/reservation (D-026, deferred)
    "QA-017",  # "Posso escolher um profissional?" — professional-choice filtering not implemented
    "QA-021",  # "Posso agendar para outra pessoa?" — identity/consent, deferred
    "QA-022",  # "Menor de idade pode ser agendado?" — identity/consent, deferred
    "QA-023",  # "Como recebo a confirmação?" — post-booking confirmation, deferred
    "QA-024",  # "Perdi meu protocolo. O que faço?" — protocol/appointment lookup, deferred (D-024)
]


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    deactivated = 0
    for qa_id in DEACTIVATE_QA_IDS:
        response = client.delete(f"/api/v1/operator/knowledge/qa/{qa_id}", headers=headers)
        assert response.status_code == 204, response.text
        deactivated += 1
    print(f"deactivated {deactivated} out-of-scope agenda Q&A entries: {', '.join(DEACTIVATE_QA_IDS)}")


if __name__ == "__main__":
    run()
