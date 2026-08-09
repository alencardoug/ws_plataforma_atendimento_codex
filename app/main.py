import asyncio
import base64
import hashlib
import os
import re
from datetime import date
from typing import Literal
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://oncology:oncology_demo_change_me@localhost:5432/oncology",
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
app = FastAPI(
    title="Referência Oncológica Cancer Center — API simulada",
    version="0.1.0",
)


def _fernet() -> Fernet:
    secret = os.getenv("CPF_ENCRYPTION_KEY", "demo-only-change-before-use-32bytes")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def clean_cpf(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11 or digits == digits[0] * 11:
        raise ValueError("CPF inválido")
    for size in (9, 10):
        total = sum(int(digits[i]) * (size + 1 - i) for i in range(size))
        check = (total * 10 % 11) % 10
        if check != int(digits[size]):
            raise ValueError("CPF inválido")
    return digits


class HoldRequest(BaseModel):
    slot_id: UUID
    full_name: str = Field(min_length=3, max_length=150)
    cpf: str
    phone: str = Field(min_length=8, max_length=30)
    email: EmailStr
    birth_date: date | None = None
    insurance_name: str | None = None
    city: str | None = None
    state_code: str | None = Field(default=None, min_length=2, max_length=2)
    reason: str | None = Field(default=None, max_length=1000)
    consent_accepted: bool
    channel: Literal["telegram", "web", "api"] = "web"

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        return clean_cpf(value)


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "simulation": True}


@app.get("/v1/specialties")
def specialties():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT slug, display_name, description
              FROM scheduling.specialties ORDER BY display_name
        """)).mappings().all()
    return {"items": [dict(r) for r in rows], "simulation": True}


@app.get("/v1/availability")
def availability(
    specialty: str,
    window: Literal["NEXT_DAY", "SEVEN_DAYS"] = "NEXT_DAY",
    reference_date: date | None = Query(default=None),
):
    ref = reference_date or date.today()
    with engine.begin() as conn:
        conn.execute(
            text("SELECT * FROM scheduling.ensure_demo_availability(:ref)"),
            {"ref": ref},
        )
        rows = conn.execute(text("""
            SELECT slot_id, offer_window, starts_at, ends_at, specialty_slug,
                   specialty_name, professional_name, fixed_price_cents,
                   unit_name
              FROM scheduling.available_offers
             WHERE specialty_slug = :specialty
               AND offer_window = :window
               AND reference_date = :ref
             ORDER BY starts_at
             LIMIT 4
        """), {"specialty": specialty, "window": window, "ref": ref}).mappings().all()
    return {
        "reference_date": ref,
        "window": window,
        "items": [dict(r) for r in rows],
        "simulation": True,
    }


@app.post("/v1/appointments/hold", status_code=201)
def hold_appointment(payload: HoldRequest):
    if not payload.consent_accepted:
        raise HTTPException(400, "É necessário aceitar o aviso de privacidade.")
    cpf = payload.cpf
    cpf_hash = hashlib.sha256(cpf.encode()).hexdigest()
    cpf_ciphertext = _fernet().encrypt(cpf.encode())

    with engine.begin() as conn:
        slot = conn.execute(text("""
            SELECT s.slot_id, s.status, ps.fixed_price_cents
              FROM scheduling.schedule_slots s
              JOIN scheduling.professional_specialties ps
                ON ps.professional_id=s.professional_id
               AND ps.specialty_id=s.specialty_id
             WHERE s.slot_id=:slot_id
             FOR UPDATE OF s
        """), {"slot_id": payload.slot_id}).mappings().first()
        if not slot or slot["status"] != "available":
            raise HTTPException(409, "Este horário não está mais disponível.")

        patient_id = conn.execute(text("""
            INSERT INTO identity.patients
                (full_name, cpf_ciphertext, cpf_hash, cpf_last4, phone, email,
                 birth_date, insurance_name, city, state_code)
            VALUES (:full_name, :ciphertext, :cpf_hash, :last4, :phone, :email,
                    :birth_date, :insurance_name, :city, :state_code)
            ON CONFLICT (cpf_hash) DO UPDATE SET
                full_name=EXCLUDED.full_name, phone=EXCLUDED.phone,
                email=EXCLUDED.email, insurance_name=EXCLUDED.insurance_name,
                city=EXCLUDED.city, state_code=EXCLUDED.state_code
            RETURNING patient_id
        """), {
            **payload.model_dump(exclude={"slot_id", "cpf", "consent_accepted", "channel", "reason"}),
            "ciphertext": cpf_ciphertext,
            "cpf_hash": cpf_hash,
            "last4": cpf[-4:],
        }).scalar_one()

        conn.execute(text("""
            INSERT INTO identity.consent_records
                (patient_id, purpose, policy_version, accepted, channel)
            VALUES (:patient_id, 'agendamento_e_assistencia', '1.0.0', true, :channel)
        """), {"patient_id": patient_id, "channel": payload.channel})

        appointment = conn.execute(text("""
            INSERT INTO scheduling.appointments
                (protocol, slot_id, patient_id, status, hold_expires_at, reason)
            VALUES (
                'ROC-' || to_char(now() AT TIME ZONE 'America/Sao_Paulo','YYYYMMDD') || '-' ||
                lpad(nextval('scheduling.appointment_events_event_id_seq')::text,6,'0'),
                :slot_id, :patient_id, 'awaiting_payment', now() + interval '30 minutes', :reason
            ) RETURNING appointment_id, protocol, hold_expires_at
        """), {"slot_id": payload.slot_id, "patient_id": patient_id, "reason": payload.reason}).mappings().one()
        conn.execute(text("UPDATE scheduling.schedule_slots SET status='held' WHERE slot_id=:slot_id"), {"slot_id": payload.slot_id})
        payment = conn.execute(text("""
            INSERT INTO billing.payments (appointment_id, amount_cents)
            VALUES (:appointment_id, :amount) RETURNING payment_id, payment_url, amount_cents
        """), {"appointment_id": appointment["appointment_id"], "amount": slot["fixed_price_cents"]}).mappings().one()

    return {
        **dict(appointment), **dict(payment),
        "cpf_display": f"***.***.***-{cpf[-2:]}",
        "message": "Horário reservado por 30 minutos (simulação).",
        "simulation": True,
    }


@app.post("/v1/appointments/{appointment_id}/simulate-payment")
async def simulate_payment(appointment_id: UUID):
    await asyncio.sleep(3)
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT a.appointment_id, a.protocol, a.slot_id, a.status,
                   a.hold_expires_at, p.payment_id, p.amount_cents, p.payment_url
              FROM scheduling.appointments a
              JOIN billing.payments p ON p.appointment_id=a.appointment_id
             WHERE a.appointment_id=:id FOR UPDATE OF a, p
        """), {"id": appointment_id}).mappings().first()
        if not row:
            raise HTTPException(404, "Agendamento não encontrado.")
        if row["status"] == "confirmed":
            return {**dict(row), "message": "Pagamento já confirmado (simulação).", "simulation": True}
        if row["status"] != "awaiting_payment":
            raise HTTPException(409, "O agendamento não aguarda pagamento.")
        conn.execute(text("""
            UPDATE billing.payments SET status='confirmed', confirmed_at=now()
             WHERE payment_id=:payment_id
        """), row)
        conn.execute(text("""
            UPDATE scheduling.appointments SET status='confirmed', confirmed_at=now()
             WHERE appointment_id=:appointment_id
        """), row)
        conn.execute(text("""
            UPDATE scheduling.schedule_slots SET status='booked' WHERE slot_id=:slot_id
        """), row)
        conn.execute(text("""
            INSERT INTO billing.payment_events(payment_id,event_type,payload)
            VALUES (:payment_id,'SIMULATED_PAYMENT_CONFIRMED',jsonb_build_object('delay_seconds', 3))
        """), row)
    return {
        **dict(row),
        "status": "confirmed",
        "message": "Pagamento confirmado (simulação). Sua consulta foi agendada com sucesso.",
        "policies_url": "/v1/policies/CANCELAMENTO",
        "simulation": True,
    }


@app.get("/v1/policies/{policy_code}")
def policy(policy_code: str):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT policy_code, version, title, body_markdown, effective_from, simulated
              FROM governance.policies WHERE policy_code=upper(:code)
             ORDER BY effective_from DESC LIMIT 1
        """), {"code": policy_code}).mappings().first()
    if not row:
        raise HTTPException(404, "Política não encontrada.")
    return dict(row)


@app.get("/v1/content/search")
def search_content(q: str, cancer_type: str | None = None, limit: int = Query(5, ge=1, le=20)):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT c.chunk_id, c.parent_document_id, c.heading, c.content_markdown,
                   c.urgency, c.metadata,
                   ts_rank_cd(c.search_vector, websearch_to_tsquery('portuguese', :q)) AS rank
              FROM content.chunks c
              JOIN content.documents d ON d.document_id=c.parent_document_id
             WHERE c.search_vector @@ websearch_to_tsquery('portuguese', :q)
               AND (:cancer_type IS NULL OR d.cancer_type=:cancer_type)
             ORDER BY rank DESC LIMIT :limit
        """), {"q": q, "cancer_type": cancer_type, "limit": limit}).mappings().all()
    return {"items": [dict(r) for r in rows]}
