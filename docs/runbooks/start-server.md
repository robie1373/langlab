# Runbook: Start / Stop Development Server

> For homelab NixOS deployment, see `DEPLOY_TODO.md` and nixos-config.

---

## Start

```bash
cd ~/proj/langlab

# Python 3 must be available. On NixOS dev, use the Nix store path:
python3 server.py

# Or with explicit Nix store Python:
/nix/store/0hpp14v08v99hbhqhldb77db8xl4zw9d-python3-3.13.12-env/bin/python3 server.py
```

Default: `http://localhost:8080`

### With a custom data directory

```bash
LANGLAB_DATA_DIR=/path/to/data python3 server.py
```

### With API keys

```bash
GEMINI_API_KEY=AIza... CLAUDE_API_KEY=... python3 server.py
```

---

## Stop

The server runs in the foreground. `Ctrl+C` to stop.

If it was started in the background:

```bash
# Find the PID
ss -tlnp | grep 8080
# Kill it
kill <pid>
```

---

## Check it's running

```bash
curl http://localhost:8080/api/users
```

Should return the users array.

---

## Run tests

```bash
cd ~/proj/langlab
python3 -m unittest discover -s tests -v
```

All tests use in-memory SQLite. Safe to run against a live data directory.

---

## Notes

- No hot-reload. Restart the server after editing Python files.
- Static frontend assets (`frontend/`) are served directly from disk — JS/CSS changes take effect on page refresh without a server restart.
- `python` is not aliased on this NixOS dev machine; use `python3` or the full Nix store path.
