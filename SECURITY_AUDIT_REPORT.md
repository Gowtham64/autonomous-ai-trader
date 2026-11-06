# Security Audit

Reviewed from source, with local requests for the two issues that were fixed. No exploit traffic was sent to the public Render host. No secrets are copied here.

## Fixed

### Unauthenticated server-side fetch on `/api/ollama/register`
- **Boundary:** Any internet client could make the API process request an arbitrary URL, including link-local metadata addresses, and then route model prompts to that host.
- **Change:** `validate_public_bridge_url` allows only public http(s) hosts. Registration returns 403 unless `OLLAMA_BRIDGE_TOKEN` matches the header `X-Bridge-Token` or the JSON `token` field. Redirects are not followed. `/api/ollama/status` no longer returns the tunnel URL.
- **Evidence:** Local POST of `http://169.254.169.254/` returned 400. POST of `https://1.1.1.1` without a token returned 403.
- **Follow-up:** Set the same `OLLAMA_BRIDGE_TOKEN` on Render and on the Mac that runs `scripts/auto_mac_bridge.py`. Until then the cloud models stay primary and the Mac tunnel is not used.

### Kill switch reset and duplicate order loops
Treated as safety defects in `BUG_FIX_REPORT.md`. They are also security-relevant because a public daemon endpoint could previously interact with a switch the process itself cleared.

## Still open

### High: unauthenticated control plane
`AUTH_REQUIRED=false` in `render.yaml` makes `get_current_user` return role `admin`. These routes then succeed without a password:

- `POST /api/kill-switch`
- `POST /api/daemon/start`, `/api/daemon/stop`, `/api/daemon/cycle`
- `POST /api/skills/execute` and other `require_admin` writes
- `POST /api/factory/agents` and delete

The dashboard is built to call them without a login. Turning auth on without setting `ADMIN_PASSWORD` and teaching the UI to send the bearer token would lock the operator out. That wiring was not changed in this pass. Set `AUTH_REQUIRED=true` and a long `ADMIN_PASSWORD` before exposing the host, or put the service behind a network allowlist.

### Medium: WebSocket is open when auth is off
`/ws/live-feed` accepts anonymous clients in that mode and sends quotes plus treasury fields. It does not send broker keys. With auth on, a missing token closes the socket.

### Medium: JWT secret
`JWT_SECRET_KEY` defaults to a new random value per process when the environment variable is unset. Tokens die on restart. Set a stable secret before enabling auth. Do not commit it.

### Medium: trade tape host
`/api/market/trades` calls Binance with an allowlisted symbol and a capped limit. That is not an open SSRF. It is a second market, so a symbol that exists on Binance and not on Delta can still show prints that the paper broker does not trade.

### Low: login comparison
`authenticate_user` still has a direct password compare before the PBKDF2 check, for a plaintext `ADMIN_PASSWORD`. Prefer a stored hash only. Empty password already fails closed (`authenticate_user` returns none when the password is empty).

## Checked and left as-is

- Path traversal on the daily report date route is rejected in `tests/test_security_audit_fixes.py`.
- Guardian exit direction tests still pass (buy to close a short, sell to close a long).
- `.gitignore` entries expected by that test are present.
- Paper mode does not print Angel One client codes on `/health`.

## Not done

No dependency CVE scan was run. No production pen-test. No review of host-level Render access controls.
