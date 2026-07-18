# MediaHub Python Engine

The embedded media-processing engine for MediaHub. Runs as a child process of
the Android foreground service and speaks line-delimited JSON-RPC over stdio.

> See `docs/ARCHITECTURE.md` and `docs/BRIDGE_CONTRACT.md` in the repo root
> for the full contract.

## Layout

```
mediahub_engine/
├── __main__.py        # entry: asyncio.run(engine.main())
├── engine.py          # Engine: owns loop, dispatch, providers
├── config.py          # frozen runtime config
├── contracts.py       # pydantic request/response models
├── ipc/jsonrpc.py     # line-delimited JSON-RPC framing + dispatch
├── download/          # queue, task, manager, strategy
├── providers/         # provider registry + per-platform modules
└── utils/logging.py   # structured stderr logging
```

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Manual IPC smoke test

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"engine.ping","params":{}}' | \
  python -m mediahub_engine
```

Expected stdout (one line):

```json
{"jsonrpc":"2.0","id":1,"result":{"pong":true,"version":"0.1.0"}}
```

## Conventions

- **stdout is JSON-RPC only.** Never `print()` debug output to stdout — use
  `mediahub_engine.utils.logging` which writes structured logs to **stderr**.
- **One JSON object per line.** The encoder guarantees compact output with no
  embedded newlines.
- **Never block the event loop.** Extraction backends (yt-dlp, gallery-dl) are
  synchronous and must run in a `ThreadPoolExecutor`.
