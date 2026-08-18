import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// v2.spec.ts's T128 scenario deliberately trips the anonymous-token
// rate limiter's per-source lockout (~60 wrong-token requests) to prove it
// engages. That lockout is IP-keyed, held in the backend process's
// in-memory state, and outlives the test — v2.spec.ts's own comment on
// T128 already documented this and required restarting the backend
// container before running other token-validation-dependent E2E scenarios
// from the same host. Adding v3.spec.ts (which now runs after v2.spec.ts
// in a full `playwright test` pass) made this a real, reproducible failure
// for the first time instead of a documented manual-workflow caveat: this
// global setup restarts the backend once before the whole suite so no
// scenario file's rate-limit state can leak into another's, in either
// direction, regardless of run order.
export default function globalSetup(): void {
  execFileSync("docker", ["compose", "restart", "backend"], { cwd: repoRoot, stdio: "inherit" });
  execFileSync("bash", ["-c", "until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 1; done"], { cwd: repoRoot, stdio: "inherit", timeout: 30_000 });
}
