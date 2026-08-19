"""005, tasks.md T061: this feature's own import-graph containment check —
complements the pre-existing tests/test_booking_script_containment.py
(AST-based, proves no new OPERATOR-authored Message construction site
exists — GB-2/GB-4 only ever create AIGeneration rows, never Message rows,
so that suite already covers this feature for free). This file adds the
one thing that suite doesn't check: that 005's own new module
(scheduling/guided_booking.py) never imports from booking_script/*, and
booking_script/* never imports guided_booking — source-level, so it stays
meaningful after this feature is committed (not a point-in-time git-diff
snapshot). specs/005-dynamic-pricing-and-guided-booking/spec.md §8 outcome
8, plan.md §2/§10."""

import inspect

from customer_care.booking_script import service
from customer_care.scheduling import guided_booking


class TestNoImportCoupling:
    def test_guided_booking_module_does_not_import_booking_script(self) -> None:
        import_lines = [line for line in inspect.getsource(guided_booking).splitlines() if line.strip().startswith(("import ", "from "))]
        assert not any("booking_script" in line for line in import_lines)

    def test_booking_script_service_does_not_import_guided_booking(self) -> None:
        import_lines = [line for line in inspect.getsource(service).splitlines() if line.strip().startswith(("import ", "from "))]
        assert not any("guided_booking" in line for line in import_lines)
