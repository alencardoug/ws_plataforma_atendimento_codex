"""T092: the human's own two CPF examples and two payment examples
verbatim, plus every case plan.md §10 lists. Pure functions, no database.
specs/004-dynamic-appointment-availability/spec.md AA-10, acceptance.md
§M."""

from customer_care.booking_script.parsing import detect_booking_intent, extract_cpf, extract_payment_confirmation


class TestExtractCpf:
    def test_human_example_ten_digits_is_invalid(self) -> None:
        assert extract_cpf("Ah 123456a8910") is None

    def test_human_example_eleven_digits_is_valid_and_formatted(self) -> None:
        assert extract_cpf("tabom 123.456..789.10") == "123.456.789-10"

    def test_twelve_digits_is_invalid(self) -> None:
        assert extract_cpf("123456789012") is None

    def test_exactly_eleven_digits_no_punctuation(self) -> None:
        assert extract_cpf("12345678901") == "123.456.789-01"

    def test_never_applies_the_real_cpf_check_digit_algorithm(self) -> None:
        # 11111111111 fails the real Brazilian CPF check-digit algorithm
        # but has exactly 11 digits — must still pass here (format-only,
        # matching the human's explicit "é uma simulação" instruction).
        assert extract_cpf("111.111.111-11") == "111.111.111-11"

    def test_empty_or_no_digits_is_invalid(self) -> None:
        assert extract_cpf("") is None
        assert extract_cpf("não tenho CPF comigo agora") is None


class TestExtractPaymentConfirmation:
    def test_human_example_negative_sentence(self) -> None:
        assert extract_payment_confirmation("Então, não paguei") is False

    def test_human_example_affirmative_sentence(self) -> None:
        assert extract_payment_confirmation("tabom simm paguei") is True

    def test_sim_variants_case_insensitive(self) -> None:
        for variant in ("sim", "Sim", "SIM", "simm", "SIMM"):
            assert extract_payment_confirmation(variant) is True

    def test_nao_variants_case_insensitive_and_accent_insensitive(self) -> None:
        for variant in ("não", "nao", "Não", "NÃO", "Nao"):
            assert extract_payment_confirmation(variant) is False

    def test_unrecognized_reply_is_none(self) -> None:
        assert extract_payment_confirmation("talvez amanhã") is None
        assert extract_payment_confirmation("") is None

    def test_message_matching_both_is_ambiguous_none(self) -> None:
        assert extract_payment_confirmation("sim, mas não tenho certeza") is None

    def test_word_boundary_does_not_false_positive(self) -> None:
        # "simples"/"naoenal" contain "sim"/"nao" as substrings but are not
        # the words "sim"/"não" — must not match.
        assert extract_payment_confirmation("é bem simples") is None

    def test_ten_consecutive_non_affirmative_replies_all_stay_unconfirmed(self) -> None:
        replies = ["não", "nao", "talvez", "não sei", "ainda não", "", "quem sabe", "não paguei ainda", "depois eu pago", "não"]
        for reply in replies:
            assert extract_payment_confirmation(reply) is not True


class TestDetectBookingIntent:
    def test_positive_examples(self) -> None:
        assert detect_booking_intent("Quero marcar essa consulta") is True
        assert detect_booking_intent("pode agendar para mim?") is True
        assert detect_booking_intent("Vou querer esse horário") is True

    def test_negative_examples(self) -> None:
        assert detect_booking_intent("Existe consulta disponível amanhã?") is False
        assert detect_booking_intent("Quanto custa uma consulta de mastologia?") is False
        assert detect_booking_intent("Oi, tudo bem?") is False
