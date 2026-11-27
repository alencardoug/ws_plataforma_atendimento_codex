import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// LF-5: every SQL helper must target the same disposable database as the
// backend. Refuse a missing/wrong target before any test can TRUNCATE.
export function isolatedDatabaseName(): string {
  const expected = "oncology_langfuse_test";
  if (process.env.E2E_DATABASE_NAME !== expected) {
    throw new Error("E2E_DATABASE_NAME must explicitly select oncology_langfuse_test; use the Langfuse gate runner");
  }
  const actual = execFileSync("docker", ["compose", "exec", "-T", "db", "psql", "-h", "/var/run/postgresql", "-U", "oncology", "-d", expected,
    "-At", "-v", "ON_ERROR_STOP=1", "-c", "SELECT current_database();"], { cwd: repoRoot, encoding: "utf8" }).trim();
  if (actual !== expected) throw new Error("Refusing SQL outside the isolated local test database");
  return expected;
}

export function waitForBackend(): void {
  const base = new URL(process.env.E2E_API_BASE_URL || "http://127.0.0.1:8000");
  if (!["127.0.0.1", "localhost"].includes(base.hostname)) throw new Error("E2E backend must be local");
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      execFileSync("curl", ["--fail", "--silent", new URL("/ready", base).href], { stdio: "ignore", timeout: 2000 });
      return;
    } catch {
      execFileSync("sleep", ["1"]);
    }
  }
  throw new Error("Isolated backend did not become ready within 30 seconds");
}
