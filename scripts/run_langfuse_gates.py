"""LF-5: one local executor, disposable database, both flags, automatic restore.

Run with the project's Python 3.12 development dependencies:
    .venv/bin/python scripts/run_langfuse_gates.py --stage all

The source database is read only (pg_dump of synthetic content). Only
oncology_langfuse_test may be reset. No .env or base Compose file is edited.
"""

import argparse
import fcntl
import json
import os
import secrets
import signal
import socket
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE = "oncology_langfuse_test"
REPORT = ROOT / "LANGFUSE" / "validation-report.json"


class Gates:
    def __init__(self, directory: Path, stage: str, flag: str, pytest_args: list[str]) -> None:
        self.directory, self.stage, self.flag, self.pytest_args = directory, stage, flag, pytest_args
        self.env = dict(os.environ)
        self.env.update({key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None})
        self.source_env = dict(self.env)
        self.source_env["COMPOSE_FILE"] = str(ROOT / "docker-compose.yml")
        source_url = make_url(self.env.get("DATABASE_URL", "postgresql+psycopg://oncology:oncology_demo_change_me@db:5432/oncology"))
        if source_url.host not in {"db", "localhost", "127.0.0.1"} or source_url.database == TEST_DATABASE:
            raise RuntimeError("Source must be the normal local database")
        self.source_database = source_url.database or "oncology"
        self.user = self.env.get("POSTGRES_USER", "oncology")
        if self.user != "oncology":
            raise RuntimeError("Current acceptance helpers require the local oncology role")
        self.env.update(
            LF_TEST_DATABASE_URL=source_url.set(host="db", port=5432, database=TEST_DATABASE).render_as_string(hide_password=False),
            SMOKE_OPERATOR_EMAIL="lf5-validation@example.invalid", SMOKE_OPERATOR_PASSWORD=secrets.token_urlsafe(24),
            LANGFUSE_TRACING_ENVIRONMENT="local-test", RUN_BOOTSTRAP_SEED="false",
            E2E_DATABASE_NAME=TEST_DATABASE, E2E_MATURITY_MODE="N2",
        )
        self.env["E2E_OPERATOR_EMAIL"] = self.env["SMOKE_OPERATOR_EMAIL"]
        self.env["E2E_OPERATOR_PASSWORD"] = self.env["SMOKE_OPERATOR_PASSWORD"]
        self.original_running: set[str] = set()
        self.source_started = False
        self.project = f"customer-care-lf-validation-{os.getpid()}"
        self.prepared = False
        self.report: dict[str, Any] = {"started_at": datetime.now(UTC).isoformat(), "database": TEST_DATABASE, "stage": stage, "checks": []}
        self.override = directory / "compose.validation.yaml"
        self.dump = directory / "content.sql"

    def run(self, command: list[str], label: str, *, cwd: Path = ROOT, env: dict[str, str] | None = None, timeout: int = 1200) -> None:
        print(f"[LF-5] {label}", flush=True)
        started = time.monotonic()
        completed = subprocess.run(command, cwd=cwd, env=env or self.env, timeout=timeout)
        self.report["checks"].append({"label": label, "exit_code": completed.returncode, "seconds": round(time.monotonic() - started, 2)})
        self.save_report()
        if completed.returncode:
            raise RuntimeError(f"Gate failed: {label}")

    def capture(self, command: list[str], *, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(command, cwd=ROOT, env=env or self.env, capture_output=True, text=True, timeout=60)
        if result.returncode:
            # Do not include command/env or a potentially credential-bearing
            # Docker/connection error in a traceback.
            raise RuntimeError("Local validation inspection failed")
        return result.stdout

    def compose(self, *args: str) -> list[str]:
        return ["docker", "compose", *args]

    def backend(self, *args: str, extra_env: dict[str, str] | None = None) -> list[str]:
        command = self.compose("exec", "-T", "-e", "PYTHONPATH=/app:/app/tests", "-e", "LANGFUSE_TRACING_ENABLED=" + self.env["LANGFUSE_TRACING_ENABLED"])
        for key, value in (extra_env or {}).items():
            command += ["-e", f"{key}={value}"]
        return command + ["backend", *args]

    def psql(self, database: str, sql: str, *, source: bool = False) -> str:
        return self.capture(self.compose("exec", "-T", "db", "psql", "-h", "/var/run/postgresql", "-U", self.user, "-d", database, "-At", "-v", "ON_ERROR_STOP=1", "-c", sql), env=self.source_env if source else self.env)

    def save_report(self) -> None:
        REPORT.write_text(json.dumps(self.report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def available_port(preferred: int) -> int:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", preferred))
            except OSError:
                probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])

    def prepare(self) -> None:
        # Snapshot service state before the override or any mutation.
        raw = self.capture(self.compose("ps", "--all", "--format", "json"), env=self.source_env)
        entries = json.loads(raw) if raw.lstrip().startswith("[") else [json.loads(line) for line in raw.splitlines() if line.strip()]
        self.original_running = {row["Service"] for row in entries if row["State"] == "running"}
        self.report["initial_running_services"] = sorted(self.original_running)
        self.report["source_database"] = self.source_database
        self.report["validation_project"] = self.project
        if "db" not in self.original_running:
            self.source_started = True
            self.run(self.compose("start", "db"), "start source PostgreSQL for read-only snapshot", env=self.source_env)
        deadline = time.monotonic() + 30
        while True:
            try:
                self.report["initial_autonomy"] = self.psql(self.source_database, "BEGIN READ ONLY; SELECT n5_kill_switch_enabled, autonomy_kill_switch_enabled, autonomy_window_seconds, automatic_trigger_idle_seconds FROM customer_service.system_settings; COMMIT;", source=True).strip()
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        # Preserve only synthetic knowledge; no historical conversations or
        # operator credentials are copied or exported to Langfuse.
        with self.dump.open("wb") as output:
            result = subprocess.run(self.compose("exec", "-T", "db", "pg_dump", "-U", self.user, "-d", self.source_database,
                                                "--data-only", "--schema=content", "--no-owner", "--no-privileges"), cwd=ROOT, env=self.source_env, stdout=output, stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            raise RuntimeError("Read-only synthetic knowledge snapshot failed")
        self.restore_source()
        backend_port, frontend_port = self.available_port(18000), self.available_port(15173)
        self.env.update(E2E_API_BASE_URL=f"http://127.0.0.1:{backend_port}", E2E_BASE_URL=f"http://127.0.0.1:{frontend_port}")
        dockerfile = (ROOT / "app" / "Dockerfile").read_text(encoding="utf-8")
        dockerfile = dockerfile.replace("COPY requirements.txt .", "COPY requirements.txt requirements-dev.txt .").replace("-r requirements.txt", "-r requirements-dev.txt")
        (self.directory / "Dockerfile.validation").write_text(dockerfile, encoding="utf-8")
        # YAML !override changes only the temporary port mapping. It does not
        # append a conflicting second mapping to the base Compose config.
        self.override.write_text(f'''services:
  db:
    environment:
      POSTGRES_DB: {TEST_DATABASE}
    ports: !override []
  backend:
    image: customer-care-lf-validation-backend
    build:
      context: {ROOT / "app"}
      dockerfile: {self.directory / "Dockerfile.validation"}
    ports: !override ["127.0.0.1:{backend_port}:8000"]
    volumes:
      - {ROOT / "app"}:/app:ro
    environment:
      DATABASE_URL: ${{LF_TEST_DATABASE_URL}}
      AI_PROVIDER: openai
      RUN_BOOTSTRAP_SEED: "false"
      LANGFUSE_TRACING_ENABLED: ${{LANGFUSE_TRACING_ENABLED:-false}}
      LANGFUSE_TRACING_ENVIRONMENT: local-test
      LANGFUSE_PUBLIC_KEY: ${{LANGFUSE_PUBLIC_KEY:-}}
      LANGFUSE_SECRET_KEY: ${{LANGFUSE_SECRET_KEY:-}}
      LANGFUSE_BASE_URL: ${{LANGFUSE_BASE_URL:-}}
      LANGFUSE_HOST: ${{LANGFUSE_HOST:-}}
      SMOKE_OPERATOR_EMAIL: ${{SMOKE_OPERATOR_EMAIL}}
      SMOKE_OPERATOR_PASSWORD: ${{SMOKE_OPERATOR_PASSWORD}}
  frontend:
    image: customer-care-lf-validation-frontend
    ports: !override ["127.0.0.1:{frontend_port}:80"]
''', encoding="utf-8")
        self.env["COMPOSE_FILE"] = str(ROOT / "docker-compose.yml") + os.pathsep + str(self.override)
        self.env["COMPOSE_PROJECT_NAME"] = self.project
        self.env["LANGFUSE_TRACING_ENABLED"] = "false"
        self.prepared = True
        self.run(self.compose("build", "--quiet", "backend", "frontend"), "build validation images", timeout=1800)
        self.run(self.compose("up", "-d", "--wait", "db"), "start isolated PostgreSQL")
        self.run(self.compose("up", "-d", "--no-deps", "--force-recreate", "backend"), "start isolated backend")
        self.run(self.backend("python", "-m", "alembic", "upgrade", "head"), "migrate isolated database")
        self.restore_content()
        self.run(self.backend("python", "tests/langfuse_gate_support.py", "seed-operator"), "seed synthetic test operator")

    def restore_content(self) -> None:
        self.run(self.backend("python", "tests/langfuse_gate_support.py", "reset-content"), "reset isolated fixtures")
        if self.psql(TEST_DATABASE, "SELECT current_database()").strip() != TEST_DATABASE:
            raise RuntimeError("Refusing restore into an unverified database")
        with self.dump.open("rb") as source:
            result = subprocess.run(self.compose("exec", "-T", "db", "psql", "-U", self.user, "-d", TEST_DATABASE, "-v", "ON_ERROR_STOP=1"),
                                    cwd=ROOT, env=self.env, stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            raise RuntimeError("Synthetic content restore failed")
        self.psql(TEST_DATABASE, "UPDATE content.categories SET autonomy_enabled=false")

    def execute(self) -> None:
        flags = ("false", "true") if self.flag == "both" else (self.flag,)
        for flag in flags:
            self.env["LANGFUSE_TRACING_ENABLED"] = flag
            self.run(self.compose("up", "-d", "--no-deps", "--force-recreate", "backend"), f"tracing={flag}: recreate backend")
            if self.stage in {"backend", "all"}:
                self.restore_content()
                self.run(self.backend("ruff", "check", "--no-cache", "customer_care", "tests"), f"tracing={flag}: ruff")
                self.run(self.backend("mypy", "--cache-dir=/tmp/lf-mypy", "customer_care"), f"tracing={flag}: mypy")
                self.run(self.backend("python", "-m", "pytest", "-p", "langfuse_pytest_fixtures", "-q", "-o", "cache_dir=/tmp/lf-pytest", *(self.pytest_args or ["tests"]), extra_env={"AI_PROVIDER": "deterministic-test"}), f"tracing={flag}: pytest", timeout=1200)
            if self.stage in {"frontend", "all"}:
                for command in ("lint", "typecheck", "test", "build"):
                    self.run(["npm", "run", command], f"tracing={flag}: frontend {command}", cwd=ROOT / "frontend")
            if self.stage in {"smoke", "all"}:
                for path in sorted((ROOT / "app" / "tests").glob("smoke_*.py")):
                    self.restore_content()
                    if path.stem in {"smoke_n2", "smoke_v3_taxonomy_hcr"}:
                        self.run(self.backend("python", "tests/langfuse_gate_support.py", "smoke", "smoke_core"), f"tracing={flag}: core fixture for {path.stem}")
                    extra = {"GLOBAL_MATURITY_MODE": "N1", "SMOKE_EXPECT_SEARCH_ENABLED": "true"} if path.stem == "smoke_resilience" else {}
                    self.run(self.backend("python", "tests/langfuse_gate_support.py", "smoke", path.stem, extra_env=extra), f"tracing={flag}: {path.stem}", timeout=600)
                    if flag == "true" and path.stem == "smoke_v11_ungoverned_n5":
                        proof = self.capture(self.backend("python", "tests/langfuse_cloud_verification.py"))
                        self.report["cloud_proof"] = json.loads(proof)
                        self.save_report()
                        print("[LF-5] correlated Cloud traces, evidence, messages and cost confirmed", flush=True)
            if self.stage in {"e2e", "all"}:
                self.restore_content()
                self.run(self.compose("up", "-d", "--no-deps", "--force-recreate", "frontend"), f"tracing={flag}: isolated frontend")
                self.run(["npm", "run", "test:e2e"], f"tracing={flag}: Playwright", cwd=ROOT / "frontend", timeout=1800)

    def restore_source(self) -> None:
        try:
            if "initial_autonomy" in self.report:
                current = self.psql(self.source_database, "BEGIN READ ONLY; SELECT n5_kill_switch_enabled, autonomy_kill_switch_enabled, autonomy_window_seconds, automatic_trigger_idle_seconds FROM customer_service.system_settings; COMMIT;", source=True).strip()
                if current != self.report["initial_autonomy"]:
                    raise RuntimeError("Source autonomy settings changed during validation")
                self.report["source_autonomy_unchanged"] = True
        finally:
            if self.source_started:
                self.run(self.compose("stop", "db"), "restore source PostgreSQL stopped state", env=self.source_env)
                self.source_started = False

    def restore(self) -> None:
        try:
            if self.prepared:
                # This unique project/volume was created solely by this run;
                # the source project and its data volume are never removed.
                if self.env.get("COMPOSE_PROJECT_NAME") != self.project or not self.project.startswith("customer-care-lf-validation-"):
                    raise RuntimeError("Refusing cleanup of an unverified Compose project")
                self.run(self.compose("down", "--volumes"), "remove disposable validation containers and database")
        finally:
            if self.source_started:
                self.restore_source()
        self.report["restored"] = True
        self.save_report()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["prepare", "backend", "frontend", "smoke", "e2e", "all"], default="all")
    parser.add_argument("--flag", choices=["false", "true", "both"], default="both")
    parser.add_argument("--pytest-args", nargs="*")
    args = parser.parse_args()

    def interrupted(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    with Path("/tmp/customer-care-langfuse-gates.lock").open("w") as lock, tempfile.TemporaryDirectory(prefix=".lf-validation-", dir=ROOT / "app") as directory:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gates = Gates(Path(directory), args.stage, args.flag, args.pytest_args or [])
        try:
            gates.prepare()
            gates.execute()
            gates.report["result"] = "passed"
            return 0
        except (Exception, KeyboardInterrupt) as error:
            gates.report["result"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
            gates.report["error_class"] = type(error).__name__
            print(f"[LF-5] Validation stopped: {type(error).__name__}", flush=True)
            return 1
        finally:
            try:
                gates.restore()
            finally:
                gates.report["finished_at"] = datetime.now(UTC).isoformat()
                gates.save_report()


if __name__ == "__main__":
    raise SystemExit(main())
