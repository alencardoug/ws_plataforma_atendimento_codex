"""LF-5 only: legacy modules consume a populated synthetic agenda.

The earlier AA-9 module deliberately clears D+1/D+7 during its cleanup,
so seed this prerequisite at the consumer module boundary, not suite start.
Never loaded by the application or ordinary pytest without the gate runner.
"""

import pytest

from langfuse_gate_support import seed_agenda


@pytest.fixture(scope="module", autouse=True)
def legacy_agenda_fixture(request):
    if request.module.__name__.rsplit(".", 1)[-1] in {"test_availability_continuity", "test_booking_offer_draft"}:
        seed_agenda()
