## llama-balancer

A lightweight load balancer and reverse proxy for OpenAI-compatible API servers, well-suited for experimentation. It monitors multiple backend LLM servers, performs model-name-based routing, and selects per-model instances (model, model-2, ...). It supports sticky sessions to reuse prompt caches by routing repeat requests to the same instance, enforces per-server concurrency limits, exposes its own load based on GPU utilization, and ships with a simple monitoring UI.

### Features
- **Model-name routing**: Distributes requests to server groups using regex patterns defined in `server-list.json`.
- **Per-instance selection**: Prefers available instances among `model`, `model-2`, `model-3`, ...
- **Sticky sessions**: Keeps routing pinned per client (IP or username in the system message) × model for a limited time (default 3 minutes).
- **Concurrency limits**: Selects backends so that no server exceeds its `request-max`.
- **Health monitoring + UI**: Polls each backend’s `/llmhealth` every second; view status at `/llmhealth-monitor`.
- **GPU utilization on Windows/NVML**: Measures local GPU load via `win32pdh` or `pynvml`.
- **OpenAI-compatible proxy**: Routes `/v1/chat/completions` by model; all other requests are proxied to the fallback.

## Platform
- Tested on Windows.
- Not tested on Linux (GPU metrics collection may not work).
- Implemented with Flask; not intended for high-volume production traffic.

## How to Run

### Quick Start (Windows)

Run this single command to automatically download and execute the setup script.
Nothing is required including Git or Python - all portable versions are automatically downloaded and set up in ./workspace:

```bash
curl -L -o "run-llama-balancer.bat" "https://raw.githubusercontent.com/issixx/llama-balancer/main/run-llama-balancer.bat" && call run-llama-balancer.bat
```

### Manual Setup

```bash
git clone https://github.com/issixx/llama-balancer.git
cd llama-balancer
pip install -r requirements.txt
python llama-balancer-server.py
```

- The default port is `18000`.
- Please create a server-list.json in this directory, using the example below as a reference.

### Create a server-list.json

Define backend servers and model routing rules in `server-list.json`.

```json
{
  "servers": {
    "PC1": { "addr": "http://192.168.1.20", "health-port": 18000, "model-port": 8081, "request-max": 1 },
    "PC2": { "addr": "http://192.168.1.21", "health-port": 18000, "model-port": 8081 }
  },
  "models": {
    "gpt-oss:20b-64k.*": [
      "PC1",
      "PC2"
    ],
    "gpt-oss:20b-128k.*": [
      "PC1"
    ]
  },
  "fallback_server": "PC2"
}
```

- **servers**: For each server, specify `addr` (base URL including scheme), `health-port` (health endpoint), `model-port` (model API), and optional `request-max` (max concurrent in-flight requests).
- **models**: Regex pattern → list of eligible server names. Evaluated in order. If all attempts fail, the first server is used.
- **fallback_server**: Server name to use when no pattern matches.

You can override the config file path via the `SERVER_LIST_JSON` environment variable (default: `server-list.json`).

## Usage

- OpenAI-compatible API endpoints
- Use this in place of llama-server or llama-swap

## Endpoints

- `GET /llmhealth`
  - Returns the balancer’s own health (idle/busy based on local GPU utilization).
- `GET /llmhealth-snapshot`
  - Returns a JSON snapshot of recent backend states, in-flight counts, sticky entries, etc.
- `GET /llmhealth-monitor`
  - Minimal dashboard viewable in a browser.
- `GET /v1/models`
  - Returns a merged list of models across all backends (excludes hyphen-numbered variants like `-2`, `-3`).
- `/*` (everything else)
  - Reverse proxy. Removes hop-by-hop headers; request/response bodies are largely passed through.
  - Only for `/v1/chat/completions`, the model name may be rewritten when selecting an instance.

## How it works (overview)

- **Health monitoring**: Polls each backend at `addr:health-port/llmhealth` every second. Uses a conservative 5-second sliding window to judge state (idle/busy/invalid).
- **GPU load threshold**: The balancer is considered busy if the maximum GPU utilization over the last 5 seconds is ≥ 50%.
- **Sticky sessions**: Keyed by client identifier (IP or username in the system message) × model. Default TTL is 3 minutes.
- **Concurrency**: When `request-max` is set, new requests are avoided once the total in-flight count across all models on that server reaches the limit.
- **Instance selection**: Prefer available instances among `model`, `model-2`, ... If none are free, prefer backends currently `idle`.
- **Per-model rules**: Regex patterns in `models` are evaluated with `fullmatch`.

## Request monitoring

- Monitor request status at `/llmhealth-monitor` (auto-refresh every 5 seconds).

## Security notes

- This project is intended for evaluation within a private network.
- Not intended for large groups or exposure to public networks.

## Development / Contributions

- Contributions (issues, PRs, improvement proposals) are welcome. Please follow the standard GitHub flow.
- Bug fixes, optimizations, and sharing benchmark results are also welcome.

## License

- `MIT`
- See [LICENSE](LICENSE).

## Frequently Asked Questions (FAQ)

- Q: Are endpoints other than `/v1/chat/completions` routed per model?
  - A: No. Model-aware routing/optimization applies only to `POST /v1/chat/completions`. Other endpoints are proxied to the fallback server.
- Q: Does it run on non-Windows platforms?
  - A: Likely, but we have not tested on Linux. If `win32pdh` is unavailable, `pynvml` is used; if neither is available, GPU utilization is treated as 0%.
- Q: What are the timeouts?
  - A: 5s connect (2s read for health checks). For upstream proxying, the default connect timeout is 300s.


