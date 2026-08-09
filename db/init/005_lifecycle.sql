CREATE OR REPLACE FUNCTION scheduling.release_expired_holds()
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE v_count integer;
BEGIN
    WITH expired AS (
        UPDATE scheduling.appointments
           SET status='cancelled', cancelled_at=now(), cancellation_reason='hold_expired'
         WHERE status IN ('held','awaiting_payment') AND hold_expires_at < now()
         RETURNING slot_id
    )
    UPDATE scheduling.schedule_slots s SET status='available'
      FROM expired e WHERE s.slot_id=e.slot_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

CREATE OR REPLACE FUNCTION scheduling.mark_no_show(p_appointment_id uuid)
RETURNS TABLE(retained_cents integer, refunded_cents integer)
LANGUAGE plpgsql
AS $$
DECLARE v_payment billing.payments%ROWTYPE;
BEGIN
    SELECT * INTO v_payment FROM billing.payments
     WHERE appointment_id=p_appointment_id FOR UPDATE;
    IF NOT FOUND OR v_payment.status <> 'confirmed' THEN
        RAISE EXCEPTION 'Pagamento confirmado não encontrado';
    END IF;
    retained_cents := round(v_payment.amount_cents * 0.30)::integer;
    refunded_cents := v_payment.amount_cents - retained_cents;
    UPDATE scheduling.appointments SET status='no_show' WHERE appointment_id=p_appointment_id;
    UPDATE billing.payments
       SET status='partially_refunded', refunded_cents=refunded_cents
     WHERE payment_id=v_payment.payment_id;
    INSERT INTO billing.payment_events(payment_id,event_type,payload)
    VALUES (v_payment.payment_id,'NO_SHOW_PARTIAL_REFUND',
            jsonb_build_object('retention_percent',30,'retained_cents',retained_cents,
                               'refunded_cents',refunded_cents,'simulation',true));
    RETURN NEXT;
END;
$$;

