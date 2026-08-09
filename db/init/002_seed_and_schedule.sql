INSERT INTO scheduling.units (unit_id, name)
VALUES ('10000000-0000-0000-0000-000000000001', 'Unidade Central (simulação)');

INSERT INTO scheduling.specialties (specialty_id, slug, display_name, description) VALUES
('20000000-0000-0000-0000-000000000001', 'mastologia-oncologica', 'Mastologia oncológica', 'Primeira consulta para suspeita ou diagnóstico de câncer de mama (simulação)'),
('20000000-0000-0000-0000-000000000002', 'cirurgia-colorretal', 'Cirurgia colorretal oncológica', 'Primeira consulta para suspeita ou diagnóstico colorretal (simulação)'),
('20000000-0000-0000-0000-000000000003', 'segunda-opiniao', 'Segunda opinião oncológica', 'Revisão de diagnóstico, exames e proposta terapêutica (simulação)');

INSERT INTO scheduling.professionals (professional_id, display_name, registration_display) VALUES
('30000000-0000-0000-0000-000000000001', 'Dra. Helena Martins (simulação)', 'CRM-SP 000001 (simulação)'),
('30000000-0000-0000-0000-000000000002', 'Dra. Marina Lopes (simulação)', 'CRM-SP 000002 (simulação)'),
('30000000-0000-0000-0000-000000000003', 'Dra. Beatriz Nogueira (simulação)', 'CRM-SP 000003 (simulação)'),
('30000000-0000-0000-0000-000000000004', 'Dr. Rafael Almeida (simulação)', 'CRM-SP 000004 (simulação)'),
('30000000-0000-0000-0000-000000000005', 'Dr. Gustavo Mendes (simulação)', 'CRM-SP 000005 (simulação)'),
('30000000-0000-0000-0000-000000000006', 'Dra. Lívia Rocha (simulação)', 'CRM-SP 000006 (simulação)'),
('30000000-0000-0000-0000-000000000007', 'Dra. Camila Torres (simulação)', 'CRM-SP 000007 (simulação)'),
('30000000-0000-0000-0000-000000000008', 'Dr. André Ferreira (simulação)', 'CRM-SP 000008 (simulação)'),
('30000000-0000-0000-0000-000000000009', 'Dra. Paula Azevedo (simulação)', 'CRM-SP 000009 (simulação)');

INSERT INTO scheduling.professional_specialties
    (professional_id, specialty_id, fixed_price_cents, appointment_duration_minutes)
VALUES
('30000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',98000,60),
('30000000-0000-0000-0000-000000000002','20000000-0000-0000-0000-000000000001',98000,60),
('30000000-0000-0000-0000-000000000003','20000000-0000-0000-0000-000000000001',98000,60),
('30000000-0000-0000-0000-000000000004','20000000-0000-0000-0000-000000000002',105000,60),
('30000000-0000-0000-0000-000000000005','20000000-0000-0000-0000-000000000002',105000,60),
('30000000-0000-0000-0000-000000000006','20000000-0000-0000-0000-000000000002',105000,60),
('30000000-0000-0000-0000-000000000007','20000000-0000-0000-0000-000000000003',145000,90),
('30000000-0000-0000-0000-000000000008','20000000-0000-0000-0000-000000000003',145000,90),
('30000000-0000-0000-0000-000000000009','20000000-0000-0000-0000-000000000003',145000,90);

INSERT INTO scheduling.holidays (holiday_date, name, scope, state_code, city_code) VALUES
('2026-01-01','Confraternização Universal','national',NULL,NULL),
('2026-04-03','Paixão de Cristo','national',NULL,NULL),
('2026-04-21','Tiradentes','national',NULL,NULL),
('2026-05-01','Dia Mundial do Trabalho','national',NULL,NULL),
('2026-09-07','Independência do Brasil','national',NULL,NULL),
('2026-10-12','Nossa Senhora Aparecida','national',NULL,NULL),
('2026-11-02','Finados','national',NULL,NULL),
('2026-11-15','Proclamação da República','national',NULL,NULL),
('2026-11-20','Dia Nacional de Zumbi e da Consciência Negra','national',NULL,NULL),
('2026-12-25','Natal','national',NULL,NULL),
('2026-01-25','Aniversário de São Paulo','municipal','SP','SAO_PAULO'),
('2026-07-09','Revolução Constitucionalista','state','SP',NULL),
('2027-01-01','Confraternização Universal','national',NULL,NULL),
('2027-04-21','Tiradentes','national',NULL,NULL),
('2027-05-01','Dia Mundial do Trabalho','national',NULL,NULL),
('2027-09-07','Independência do Brasil','national',NULL,NULL),
('2027-10-12','Nossa Senhora Aparecida','national',NULL,NULL),
('2027-11-02','Finados','national',NULL,NULL),
('2027-11-15','Proclamação da República','national',NULL,NULL),
('2027-11-20','Dia Nacional de Zumbi e da Consciência Negra','national',NULL,NULL),
('2027-12-25','Natal','national',NULL,NULL)
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION scheduling.next_business_day(p_date date)
RETURNS date
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_date date := p_date;
BEGIN
    LOOP
        -- Sábado é dia de atendimento; domingo e feriados não são.
        IF extract(isodow FROM v_date) <> 7
           AND NOT EXISTS (
               SELECT 1 FROM scheduling.holidays h
               WHERE h.holiday_date = v_date AND NOT h.is_business_day
           ) THEN
            RETURN v_date;
        END IF;
        v_date := v_date + 1;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION scheduling.ensure_demo_availability(
    p_reference_date date DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date
)
RETURNS TABLE (specialty_slug text, offer_window text, target_date date, offers_created integer)
LANGUAGE plpgsql
AS $$
DECLARE
    v_specialty record;
    v_window text;
    v_offset integer;
    v_target date;
    v_batch uuid;
    v_i integer;
    v_hour integer;
    v_professional uuid;
    v_duration integer;
    v_slot uuid;
    v_created integer;
BEGIN
    FOR v_specialty IN SELECT * FROM scheduling.specialties ORDER BY slug LOOP
        FOREACH v_window IN ARRAY ARRAY['NEXT_DAY','SEVEN_DAYS'] LOOP
            v_offset := CASE WHEN v_window = 'NEXT_DAY' THEN 1 ELSE 7 END;
            v_target := scheduling.next_business_day(p_reference_date + v_offset);
            v_batch := gen_random_uuid();
            v_created := 0;

            -- Somente quatro vagas físicas por especialidade/data. Vagas antigas
            -- podem ser reapresentadas em outra janela sem serem duplicadas.
            FOR v_i IN 1..4 LOOP
                v_hour := CASE
                    WHEN extract(isodow FROM v_target) = 6 THEN 7 + v_i -- 08,09,10,11
                    WHEN v_i = 1 THEN 9
                    WHEN v_i = 2 THEN 11
                    WHEN v_i = 3 THEN 14
                    ELSE 16
                END;

                SELECT ps.professional_id, ps.appointment_duration_minutes
                  INTO v_professional, v_duration
                  FROM scheduling.professional_specialties ps
                 WHERE ps.specialty_id = v_specialty.specialty_id
                 ORDER BY ps.professional_id
                 OFFSET ((v_i - 1) % 3) LIMIT 1;

                INSERT INTO scheduling.schedule_slots
                    (unit_id, specialty_id, professional_id, starts_at, ends_at)
                VALUES (
                    '10000000-0000-0000-0000-000000000001',
                    v_specialty.specialty_id,
                    v_professional,
                    make_timestamptz(extract(year FROM v_target)::int,
                                     extract(month FROM v_target)::int,
                                     extract(day FROM v_target)::int,
                                     v_hour, 0, 0, 'America/Sao_Paulo'),
                    make_timestamptz(extract(year FROM v_target)::int,
                                     extract(month FROM v_target)::int,
                                     extract(day FROM v_target)::int,
                                     v_hour, 0, 0, 'America/Sao_Paulo') + make_interval(mins => v_duration)
                )
                ON CONFLICT (professional_id, starts_at) DO UPDATE
                    SET specialty_id = EXCLUDED.specialty_id
                RETURNING slot_id INTO v_slot;

                INSERT INTO scheduling.slot_offers
                    (slot_id, specialty_id, offer_window, reference_date,
                     eligible_from, eligible_until, generation_batch_id)
                VALUES (
                    v_slot, v_specialty.specialty_id, v_window, p_reference_date,
                    make_timestamptz(extract(year FROM p_reference_date)::int,
                                     extract(month FROM p_reference_date)::int,
                                     extract(day FROM p_reference_date)::int,
                                     0, 0, 0, 'America/Sao_Paulo'),
                    make_timestamptz(extract(year FROM p_reference_date)::int,
                                     extract(month FROM p_reference_date)::int,
                                     extract(day FROM p_reference_date)::int,
                                     23, 59, 59, 'America/Sao_Paulo'),
                    v_batch
                ) ON CONFLICT ON CONSTRAINT slot_offers_slot_id_offer_window_reference_date_key DO NOTHING;
                IF FOUND THEN v_created := v_created + 1; END IF;
            END LOOP;
            specialty_slug := v_specialty.slug;
            offer_window := v_window;
            target_date := v_target;
            offers_created := v_created;
            RETURN NEXT;
        END LOOP;
    END LOOP;
END;
$$;

CREATE OR REPLACE VIEW scheduling.available_offers AS
SELECT
    o.offer_id, o.offer_window, o.reference_date,
    s.slot_id, s.starts_at, s.ends_at,
    sp.slug AS specialty_slug, sp.display_name AS specialty_name,
    p.display_name AS professional_name,
    ps.fixed_price_cents,
    u.name AS unit_name
FROM scheduling.slot_offers o
JOIN scheduling.schedule_slots s ON s.slot_id = o.slot_id
JOIN scheduling.specialties sp ON sp.specialty_id = s.specialty_id
JOIN scheduling.professionals p ON p.professional_id = s.professional_id
JOIN scheduling.professional_specialties ps
  ON ps.professional_id = s.professional_id AND ps.specialty_id = s.specialty_id
JOIN scheduling.units u ON u.unit_id = s.unit_id
WHERE s.status = 'available';

INSERT INTO governance.policies
    (policy_code, version, title, body_markdown, effective_from)
VALUES
('CANCELAMENTO','1.0.0','Cancelamento e reagendamento (simulação)',
'Reagendamento sem custo até 24 horas antes. Em caso de falta sem cancelamento, a política simulada prevê retenção de 30% do valor e devolução de 70%. O direito de arrependimento e demais direitos previstos na legislação brasileira aplicável são preservados. Se a instituição cancelar, o paciente pode reagendar ou receber devolução integral.',
CURRENT_DATE),
('PRIVACIDADE','1.0.0','Privacidade no agendamento (simulação)',
'Os dados são usados para identificar o paciente, realizar o agendamento e prestar atendimento. CPF e dados de saúde não são enviados a embeddings. O paciente pode solicitar informações sobre o tratamento dos seus dados pelo Ramal 0000 (simulação).',
CURRENT_DATE);

SELECT * FROM scheduling.ensure_demo_availability(CURRENT_DATE);
