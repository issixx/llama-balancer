import os
import json
import sys
import threading
import time
# New imports for refactoring
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple, Pattern
import re

import requests
from flask import Flask, Response, jsonify, request, stream_with_context


# ------------------------------
# Configuration
# ------------------------------

# Servers configuration loaded from server-list.json only (no env overrides)
# Health check base URLs (addr:health-port) are generated dynamically.
# Actual proxying uses model ports (addr:model-port).

# Server definitions
SERVER_CONFIGS: Dict[str, Dict[str, Any]] = {}

# Regex patterns (maintaining definition order): (compiled_pattern, server_names, pattern_string)
MODEL_PATTERN_LIST: List[Tuple[Pattern[str], List[str], str]] = []

# Fallback is set to model-side base URL (addr:model-port)
FALLBACK_BACKEND: Optional[str] = None

# Optional JSON config file path
SERVER_LIST_JSON = os.getenv("SERVER_LIST_JSON", "server-list.json")





def _apply_servers_config(servers: Dict[str, Dict[str, Any]]) -> None:
    # servers: {name: {addr, health-port, model-port, request-max}}
    global SERVER_CONFIGS
    SERVER_CONFIGS = {}
    for name, cfg in (servers or {}).items():
        if not isinstance(name, str) or not isinstance(cfg, dict):
            continue
        addr = cfg.get("addr")
        hport = cfg.get("health-port")
        mport = cfg.get("model-port")
        request_max = cfg.get("request-max")
        if not isinstance(addr, str) or not isinstance(hport, int) or not isinstance(mport, int):
            continue
        addr_s = addr.rstrip("/")
        config = {"addr": addr_s, "health-port": hport, "model-port": mport}
        if isinstance(request_max, int) and request_max > 0:
            config["request-max"] = request_max
        SERVER_CONFIGS[name] = config


def _apply_model_server_list(models: Dict[str, List[str]], fallback_server_name: Optional[str]) -> None:
    # Apply new schema (models: {pattern: [server_names...]})
    global MODEL_PATTERN_LIST, FALLBACK_BACKEND
    pattern_list: List[Tuple[Pattern[str], List[str], str]] = []
    for pattern_str, server_names in (models or {}).items():
        if not isinstance(pattern_str, str) or not isinstance(server_names, list):
            continue
        # Only validate server names
        valid_names: List[str] = []
        for n in server_names:
            if isinstance(n, str) and n in SERVER_CONFIGS:
                valid_names.append(n)
        if not valid_names:
            continue
        try:
            compiled = re.compile(pattern_str)
            pattern_list.append((compiled, valid_names, pattern_str))
        except re.error:
            # Skip invalid regex patterns
            pass
    MODEL_PATTERN_LIST = pattern_list
    # Resolve fallback from server name to model base URL
    if isinstance(fallback_server_name, str) and fallback_server_name in SERVER_CONFIGS:
        FALLBACK_BACKEND = _get_model_base_url(fallback_server_name)
    else:
        # When unspecified, use any (first model base URL)
        model_urls = _get_model_base_urls()
        FALLBACK_BACKEND = model_urls[0] if model_urls else None

def _load_servers_from_json() -> None:
    try:
        with open(SERVER_LIST_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        servers = data.get("servers") if isinstance(data, dict) else None
        models = data.get("models") if isinstance(data, dict) else None
        # backward compat fallback key; new key is fallback_server
        fallback_server = data.get("fallback_server") if isinstance(data, dict) else None

        if isinstance(servers, dict) and len(servers) > 0:
            _apply_servers_config(servers)
            _apply_model_server_list(models if isinstance(models, dict) else {}, fallback_server if isinstance(fallback_server, str) else None)
        elif isinstance(models, dict) and len(models) > 0:
            # Legacy schema: case where models contains base URLs (kept for compatibility)
            _apply_model_server_list(models, fallback_server if isinstance(fallback_server, str) else None)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[WARN] Failed to load {SERVER_LIST_JSON}: {e}", file=sys.stderr)

def _get_health_base_url(server_name: str) -> Optional[str]:
    """Get health check base URL for specified server name"""
    config = SERVER_CONFIGS.get(server_name)
    if not config:
        return None
    addr = config.get("addr")
    hport = config.get("health-port")
    if not isinstance(addr, str) or not isinstance(hport, int):
        return None
    return f"{addr.rstrip('/')}:{hport}"

def _get_model_base_url(server_name: str) -> Optional[str]:
    """Get model base URL for specified server name"""
    config = SERVER_CONFIGS.get(server_name)
    if not config:
        return None
    addr = config.get("addr")
    mport = config.get("model-port")
    if not isinstance(addr, str) or not isinstance(mport, int):
        return None
    return f"{addr.rstrip('/')}:{mport}"

def _get_health_base_urls() -> List[str]:
    """Dynamically get list of health check base URLs"""
    urls = []
    for server_name in SERVER_CONFIGS.keys():
        url = _get_health_base_url(server_name)
        if url:
            urls.append(url)
    return urls

def _get_model_base_urls() -> List[str]:
    """Dynamically get list of model base URLs"""
    urls = []
    for server_name in SERVER_CONFIGS.keys():
        url = _get_model_base_url(server_name)
        if url:
            urls.append(url)
    return urls

def _get_model_backends_for_pattern(pattern: str) -> List[str]:
    """Get list of server names corresponding to specified pattern string"""
    for compiled_pattern, server_names, pattern_str in MODEL_PATTERN_LIST:
        if pattern_str == pattern:
            return server_names
    return []

def _get_model_backends_for_model(model: str) -> List[str]:
    """Get list of server names corresponding to specified model name (regex match)"""
    for compiled_pattern, server_names, _ in MODEL_PATTERN_LIST:
        try:
            if compiled_pattern.fullmatch(model):
                return server_names
        except Exception:
            continue
    return []

def _get_modelurl_by_health_base(health_base: str) -> Optional[str]:
    """Get model URL from health check base URL"""
    for server_name in SERVER_CONFIGS.keys():
        if _get_health_base_url(server_name) == health_base:
            return _get_model_base_url(server_name)
    return None

# Health polling intervals and windows
SAMPLE_INTERVAL_SEC = 1.0
WINDOW_SECONDS = 5
STICKY_TTL_SECONDS = 60 * 3

# New constant for invalid status (timeout / unreachable)
INVALID_STATUS_VAL = -1

# Requests timeouts
CONNECT_TIMEOUT_SEC = 5
UPSTREAM_CONNECT_TIMEOUT_SEC = 300
HEALTH_READ_TIMEOUT_SEC = 2

# ------------------------------
# Helper: interpret llmhealth text
# ------------------------------


def _interpret_llmhealth_text(text: str) -> int:
    """Map '/llmhealth' text or JSON 'status' field to internal int.

    Returns:
        0 -> idle
        1 -> busy or unknown string
    """
    t = (text or "").strip().lower()
    if t == "idle":
        return 0
    if t == "busy":
        return 1
    # Unknown values are considered busy
    return 1

# ------------------------------
# Lightweight Server Registry (compatibility)
# ------------------------------


@dataclass
class ServerConfig:
    name: str
    addr: str
    health_port: int
    model_port: int
    request_max: Optional[int] = None

    @property
    def health_base(self) -> str:
        return f"{self.addr.rstrip('/') }:{self.health_port}"

    @property
    def model_base(self) -> str:
        return f"{self.addr.rstrip('/') }:{self.model_port}"


class ServerRegistry:
    """Wrapper over existing global SERVER_CONFIGS / MODEL_PATTERN_LIST for newer classes"""

    @staticmethod
    def get_server(name: str) -> Optional[ServerConfig]:
        cfg = SERVER_CONFIGS.get(name)
        if not cfg:
            return None
        return ServerConfig(
            name, 
            cfg["addr"], 
            cfg["health-port"], 
            cfg["model-port"],
            cfg.get("request-max")
        )

    @staticmethod
    def server_names() -> List[str]:
        return list(SERVER_CONFIGS.keys())

    @staticmethod
    def health_bases() -> List[str]:
        return [_get_health_base_url(n) for n in SERVER_CONFIGS.keys() if _get_health_base_url(n)]

    @staticmethod
    def model_bases() -> List[str]:
        return [_get_model_base_url(n) for n in SERVER_CONFIGS.keys() if _get_model_base_url(n)]

    @property
    def fallback_backend(self) -> Optional[str]:
        return FALLBACK_BACKEND

    @staticmethod
    def model_backends_for_model(model: str) -> List[str]:
        return _get_model_backends_for_model(model)

    @property
    def model_patterns(self) -> List[Tuple[Pattern[str], List[str], str]]:
        return list(MODEL_PATTERN_LIST)

    @staticmethod
    def modelurl_by_health_base(base: str) -> Optional[str]:
        return _get_modelurl_by_health_base(base)


# global instance
SERVER_REGISTRY = ServerRegistry()


# Load from JSON file
_load_servers_from_json()

app = Flask(__name__)

# ------------------------------
# Request Helpers
# ------------------------------


def _get_client_ip() -> str:
    """Return client IP considering X-Forwarded-For"""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"

# ------------------------------
# Local GPU Utilization Monitor (Refactored)
# ------------------------------


class LocalGpuMonitor:
    """Sample GPU utilization and provide maximum value from recent WINDOW_SECONDS"""

    def __init__(self) -> None:
        self._window: Deque[float] = deque(maxlen=WINDOW_SECONDS)
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    # ---------- public helpers ----------
    def get_max(self) -> float:
        with self._lock:
            return max(self._window) if self._window else 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._sample_loop, name="gpu-sampler", daemon=True)
        self._thread.start()

    # ---------- internal ----------
    def _append(self, value: float) -> None:
        with self._lock:
            self._window.append(value)

    def _sample_loop(self) -> None:
        """Class method implementation of traditional _sample_local_gpu_loop"""
        while True:
            # 1) PDH
            pdh_map = self._query_gpu_engine_utilization()
            if pdh_map:
                total = sum(int(v) for v in pdh_map.values())
                approx_overall = float(min(100, total))
                self._append(approx_overall)
                time.sleep(SAMPLE_INTERVAL_SEC)
                continue

            # 2) NVML fallback
            try:
                import pynvml  # type: ignore
                pynvml.nvmlInit()
                handle_cache: List = []
                device_count = pynvml.nvmlDeviceGetCount()
                for i in range(device_count):
                    handle_cache.append(pynvml.nvmlDeviceGetHandleByIndex(i))
                max_util = 0.0
                for h in handle_cache:
                    try:
                        util = pynvml.nvmlDeviceGetUtilizationRates(h)
                        max_util = max(max_util, float(util.gpu))
                    except Exception:
                        pass
                self._append(max_util)
                time.sleep(SAMPLE_INTERVAL_SEC)
                continue
            except Exception:
                # 3) give up
                self._append(0.0)
                time.sleep(SAMPLE_INTERVAL_SEC)

    def _query_gpu_engine_utilization(self) -> Dict[str, int]:
        try:
            import win32pdh  # type: ignore
        except Exception:
            return {}

        counter_path = r"\GPU Engine(*)\Utilization Percentage"
        try:
            paths = win32pdh.ExpandCounterPath(counter_path)
        except Exception:
            return {}

        try:
            q = win32pdh.OpenQuery()
        except Exception:
            return {}

        counters: List[Tuple[str, Any]] = []
        try:
            for p in paths:
                try:
                    c = win32pdh.AddCounter(q, p)
                    counters.append((p, c))
                except Exception:
                    continue

            win32pdh.CollectQueryData(q)
            time.sleep(0.1)
            win32pdh.CollectQueryData(q)

            results: Dict[str, int] = {}
            for p, c in counters:
                try:
                    _, val = win32pdh.GetFormattedCounterValue(c, win32pdh.PDH_FMT_LONG)
                    v = int(val)
                except Exception:
                    v = 0
                m = re.search(r'\((.+?)\)', p)
                inst = m.group(1) if m else p
                results[inst] = v
            return results
        finally:
            try:
                win32pdh.CloseQuery(q)
            except Exception:
                pass


# Instance creation
LOCAL_GPU_MONITOR = LocalGpuMonitor()


# ------------------------------
# Backend Health Monitor (Refactored)
# ------------------------------


class BackendHealthMonitor:
    """Periodically poll /llmhealth of each backend and maintain state"""

    def __init__(self) -> None:
        # Maintain independent internal state
        self._windows: Dict[str, Deque[int]] = defaultdict(lambda: deque(maxlen=WINDOW_SECONDS))
        self._lock = threading.Lock()
        self._last_metrics: Dict[str, Dict[str, Any]] = {}
        self._thread: Optional[threading.Thread] = None

    # ---------- public helpers ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._poll_loop, name="server-poller", daemon=True)
        self._thread.start()

    def get_conservative_status(self, base: str) -> str:
        """Return idle/busy/invalid on the safe side based on observations from recent WINDOW_SECONDS"""
        with self._lock:
            window = self._windows.get(base)
            if not window or len(window) == 0:
                return "busy"
            if INVALID_STATUS_VAL in window:
                return "invalid"
            return "busy" if max(window) >= 1 else "idle"

    def snapshot_metrics(self, bases: List[str]) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {b: self._last_metrics.get(b) for b in bases}

    # ---------- internal ----------
    def _record(self, base: str, status_val: int, util_val: Optional[float], url: str) -> None:
        with self._lock:
            self._windows[base].append(status_val)
            now_utc = datetime.now(timezone.utc)
            self._last_metrics[base] = {
                "status": (
                    "invalid" if status_val == INVALID_STATUS_VAL else ("idle" if status_val == 0 else "busy")
                ),
                "gpu_util_max5s": util_val,
                "updated_at": now_utc.isoformat().replace("+00:00", "Z"),
                "url": url,
            }

    def _poll_loop(self) -> None:
        while True:
            health_bases = _get_health_base_urls()
            if not health_bases:
                time.sleep(SAMPLE_INTERVAL_SEC)
                continue

            started = time.time()
            for base in health_bases:
                try:
                    url = base.rstrip("/") + "/llmhealth"
                    resp = requests.get(url, timeout=(CONNECT_TIMEOUT_SEC, HEALTH_READ_TIMEOUT_SEC))
                    util_val: Optional[float] = None
                    if resp.headers.get("content-type", "").startswith("application/json"):
                        data = resp.json()
                        s = data.get("status") if isinstance(data, dict) else None
                        status_val = _interpret_llmhealth_text(s) if isinstance(s, str) else _interpret_llmhealth_text(resp.text)
                        if isinstance(data, dict):
                            util_candidate = data.get("gpu_util_max5s")
                            if isinstance(util_candidate, (int, float)):
                                util_val = float(util_candidate)
                    else:
                        status_val = _interpret_llmhealth_text(resp.text)
                except Exception:
                    status_val = INVALID_STATUS_VAL
                    util_val = None
                self._record(base, status_val, util_val, url)

            elapsed = time.time() - started
            time.sleep(max(0.0, SAMPLE_INTERVAL_SEC - elapsed))


# Instance creation
BACKEND_MONITOR = BackendHealthMonitor()


# ------------------------------
# Sticky Session Manager (Refactored)
# ------------------------------


class StickySessionManager:
    """Maintain binding between IP(+model) and backend for a certain period"""

    def __init__(self, ttl_seconds: int = STICKY_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._map: Dict[str, Tuple[str, datetime]] = {}

    # ---------- helpers ----------
    def get_backend(self, ip: str, model: Optional[str] = None) -> Optional[str]:
        now = datetime.now(timezone.utc)
        key = f"{ip}|{model}" if model else ip
        with self._lock:
            entry = self._map.get(key)
        if not entry:
            return None
        backend, last_time = entry
        if now - last_time > timedelta(seconds=self._ttl):
            self._map.pop(key, None)
            return None
        return backend

    def update_backend(self, ip: str, backend: str, model: Optional[str] = None) -> None:
        key = f"{ip}|{model}" if model else ip
        with self._lock:
            # Remove if same backend exists for same model
            keys_to_delete = [k for k, v in self._map.items() if k.split("|", 1)[1] == model and v[0] == backend]
            for k in keys_to_delete:
                self._map.pop(k, None)
            self._map[key] = (backend, datetime.now(timezone.utc))

    def cleanup(self) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [k for k, v in self._map.items() if now - v[1] > timedelta(seconds=self._ttl)]
            for k in expired:
                self._map.pop(k, None)


# Instance creation
STICKY_MANAGER = StickySessionManager()


# ------------------------------
# Access Log Manager (New)
# ------------------------------

@dataclass
class AccessLogEntry:
    """Access log entry for completions requests"""
    ip: str
    model: str
    timestamp: datetime
    username: Optional[str] = None

class AccessLogManager:
    """Manage access logs for completions requests with 1-hour retention"""
    
    def __init__(self, retention_hours: int = 1) -> None:
        self._retention_hours = retention_hours
        self._lock = threading.Lock()
        self._logs: Deque[AccessLogEntry] = deque()
    
    def log_access(self, ip: str, model: str, username: Optional[str] = None) -> None:
        """Log a completions request access"""
        with self._lock:
            entry = AccessLogEntry(
                ip=ip,
                model=model,
                timestamp=datetime.now(timezone.utc),
                username=username
            )
            self._logs.append(entry)
            self._cleanup_old_logs()
    
    def _cleanup_old_logs(self) -> None:
        """Remove logs older than retention period"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self._retention_hours)
        while self._logs and self._logs[0].timestamp < cutoff_time:
            self._logs.popleft()
    
    def get_recent_logs(self) -> List[AccessLogEntry]:
        """Get all logs within retention period"""
        with self._lock:
            self._cleanup_old_logs()
            return list(self._logs)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get access statistics for monitoring"""
        logs = self.get_recent_logs()
        now = datetime.now(timezone.utc)
        
        # Count by IP
        ip_counts = defaultdict(int)
        # Count by model
        model_counts = defaultdict(int)
        # Count by username
        username_counts = defaultdict(int)
        # Time-based data for charts
        time_series = defaultdict(int)
        
        for log in logs:
            ip_counts[log.ip] += 1
            model_counts[log.model] += 1
            if log.username:
                username_counts[log.username] += 1
            
            # Group by 1-minute intervals for time series
            ts = log.timestamp
            interval = ts.replace(second=0, microsecond=0)
            time_series[interval.isoformat()] += 1
        
        return {
            "total_requests": len(logs),
            "unique_ips": len(ip_counts),
            "unique_models": len(model_counts),
            "unique_usernames": len(username_counts),
            "ip_counts": dict(ip_counts),
            "model_counts": dict(model_counts),
            "username_counts": dict(username_counts),
            "time_series": dict(time_series),
            "retention_hours": self._retention_hours,
            "oldest_log": logs[0].timestamp.isoformat() if logs else None,
            "newest_log": logs[-1].timestamp.isoformat() if logs else None,
        }

# Global instance
ACCESS_LOG_MANAGER = AccessLogManager()

# ------------------------------
# In-flight Tracker (Refactored)
# ------------------------------


class InFlightTracker:
    """Manage concurrent request count per backend×model"""

    def __init__(self) -> None:
        # Generate independent lock and counter dictionary
        self._lock = threading.Lock()
        self._backend_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def get(self, backend: str, model: str) -> int:
        if not backend or not model:
            return 0
        with self._lock:
            return int(self._backend_counts[backend].get(model, 0))

    def get_total_for_backend(self, backend: str) -> int:
        """Get total request count for all models of specified backend"""
        if not backend:
            return 0
        with self._lock:
            return sum(self._backend_counts[backend].values())

    def can_accept_request(self, backend: str, model: str, request_max: Optional[int] = None) -> bool:
        """Check if specified backend can accept new requests"""
        if not backend or not model:
            return False
        if request_max is None:
            return True  # No limit
        with self._lock:
            current_total = sum(self._backend_counts[backend].values())
            return current_total < request_max

    def inc(self, backend: str, model: str) -> None:
        if not backend or not model:
            return
        with self._lock:
            self._backend_counts[backend][model] = int(self._backend_counts[backend].get(model, 0)) + 1

    def dec(self, backend: str, model: str) -> None:
        if not backend or not model:
            return
        with self._lock:
            cur = int(self._backend_counts[backend].get(model, 0))
        if cur <= 1:
                self._backend_counts[backend].pop(model, None)
        else:
                self._backend_counts[backend][model] = cur - 1


# Instance creation
INFLIGHT_TRACKER = InFlightTracker()


# ------------------------------
# Model Manager (cache & instance utilities)
# ------------------------------

# Default TTL for models cache (seconds)
MODELS_CACHE_TTL = 10


class ModelManager:
    """Handle model list cache retrieval and instance count calculation"""

    def __init__(self, ttl_seconds: int = MODELS_CACHE_TTL) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cache: Dict[str, Tuple[set, datetime]] = {}

    def available_models(self, backend: Optional[str]) -> set:
        if not backend:
            backend = SERVER_REGISTRY.fallback_backend or next(iter(SERVER_REGISTRY.model_bases()), None)
        if not backend:
            return set()

        now = datetime.now(timezone.utc)
        with self._lock:
            if backend in self._cache:
                models_set, expires_at = self._cache[backend]
                if expires_at > now:
                    return set(models_set)

        # Fetch from backend
        models_set: set = set()
        url = backend.rstrip("/") + "/v1/models"
        try:
            resp = requests.get(url, timeout=(CONNECT_TIMEOUT_SEC, HEALTH_READ_TIMEOUT_SEC))
            data: Any = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                data = resp.json()
            ids: List[str] = []
            if isinstance(data, dict):
                dl = data.get("data")
                if isinstance(dl, list):
                    for item in dl:
                        if isinstance(item, str):
                            ids.append(item)
                        elif isinstance(item, dict):
                            mid = item.get("id") or item.get("name")
                            if isinstance(mid, str):
                                ids.append(mid)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        ids.append(item)
                    elif isinstance(item, dict):
                        mid = item.get("id") or item.get("name")
                        if isinstance(mid, str):
                            ids.append(mid)
            models_set = set(ids)
        except Exception:
            models_set = set()

        with self._lock:
            self._cache[backend] = (set(models_set), now + timedelta(seconds=self._ttl))
        return models_set

    # -------- instance helpers --------
    def count_instances(self, backend: str, model: str) -> int:
        models_set = self.available_models(backend)
        count = 0
        if model in models_set:
            count += 1
        i = 2
        while f"{model}-{i}" in models_set:
            count += 1
            i += 1
        return count

    def instances_inflight_status(self, backend: str, model: str) -> Tuple[int, List[str]]:
        models_set = self.available_models(backend)
        total = 0
        idle_instances: List[str] = []
        candidates = [model] + [f"{model}-{i}" for i in range(2, 100)]
        for m in candidates:
            if m not in models_set:
                break
            inflight = INFLIGHT_TRACKER.get(backend, m)
            total += inflight
            if inflight == 0:
                idle_instances.append(m)
        return total, idle_instances


# Global instance
MODEL_MANAGER = ModelManager()


# ------------------------------
# Backend Selector
# ------------------------------


class BackendSelector:
    """Select optimal backend and instance name from model name and IP"""

    def select(self, ip: str, model: str) -> Tuple[Optional[str], Optional[str]]:
        """Return value: (backend_base_url, selected_model_name)"""
        backends_for_model = _get_model_backends_for_model(model)
        if not backends_for_model:
            return FALLBACK_BACKEND, model

        # Resolve server names to model base URLs, preserve order
        model_bases = [SERVER_CONFIGS[n]["addr"] + ":" + str(SERVER_CONFIGS[n]["model-port"]) for n in backends_for_model if n in SERVER_CONFIGS]
        if not model_bases:
            return FALLBACK_BACKEND, model

        # Sticky first
        sticky = STICKY_MANAGER.get_backend(ip, model=model)
        if sticky:
            # sticky is model URL. Convert to health URL for status check
            sticky_health = sticky.rsplit(":", 1)[0] + ":" + str(SERVER_CONFIGS.get(sticky.rsplit(":",1)[0].split("//")[-1], {}).get("health-port", ""))
            status = BACKEND_MONITOR.get_conservative_status(sticky_health)
            if status != "invalid":
                # Also check request-max of sticky backend
                sticky_server_name = None
                for name, config in SERVER_CONFIGS.items():
                    if config.get("addr") + ":" + str(config.get("model-port")) == sticky:
                        sticky_server_name = name
                        break
                if sticky_server_name:
                    sticky_cfg = SERVER_REGISTRY.get_server(sticky_server_name)
                    if sticky_cfg and INFLIGHT_TRACKER.can_accept_request(sticky, model, sticky_cfg.request_max):
                        return sticky, model  # Adopt sticky backend as it is valid

        # Iterate servers in configured order and return at first match (original behavior)
        for name in backends_for_model:
            # Remove "-low", "-medium", "-high" from end of model name
            modelWithoutSuffix = model
            for suffix in ["-low", "-medium", "-high"]:
                if modelWithoutSuffix.endswith(suffix):
                    modelWithoutSuffix = modelWithoutSuffix[: -len(suffix)]
                    break
            cfg = SERVER_REGISTRY.get_server(name)
            if not cfg:
                continue
            hbase = cfg.health_base
            mbase = cfg.model_base

            status = BACKEND_MONITOR.get_conservative_status(hbase)
            if status == "invalid":
                continue

            # Check request-max limit
            if not INFLIGHT_TRACKER.can_accept_request(mbase, modelWithoutSuffix, cfg.request_max):
                continue

            # Model instance count
            if MODEL_MANAGER.count_instances(mbase, modelWithoutSuffix) == 0:
                continue

            total_inflight, idle_instances = MODEL_MANAGER.instances_inflight_status(mbase, modelWithoutSuffix)

            # 1) backend idle & all instances inflight 0
            if total_inflight == 0 and status == "idle":
                return mbase, model

            # 2) If idle instance exists, adopt first idle instance
            if idle_instances:
                return mbase, idle_instances[0]

            # 3) If backend idle, adopt original model
            if status == "idle":
                return mbase, model

        # fallback: first backend
        return model_bases[0], model


# Global instance
BACKEND_SELECTOR = BackendSelector()


# ------------------------------
# Models List Cache (/v1/models)
# ------------------------------

# Default TTL for models cache (seconds)
MODELS_CACHE_TTL_SECONDS = 10
_models_cache_lock = threading.Lock()
# Backend-specific cache: {backend: (models_set, expires_at)}
_models_cache: Dict[str, Tuple[set, datetime]] = {}


def _get_available_models_set(backend: Optional[str] = None) -> set:
    """Get available model set from specified backend
    
    Args:
        backend: Backend base URL. Uses fallback backend if None
        
    Returns:
        Set of model names
    """
    global _models_cache
    now = datetime.now(timezone.utc)
    
    # Use fallback if backend is not specified
    if not backend:
        backend = FALLBACK_BACKEND or next(iter(_get_model_base_urls()), None)
    
    if not backend:
        return set()
    
    # Check cache
    with _models_cache_lock:
        if backend in _models_cache:
            models_set, expires_at = _models_cache[backend]
            if expires_at > now:
                return set(models_set)
    
    # Fetch if cache is invalid or does not exist
    models_set: set = set()
    url = backend.rstrip("/") + "/v1/models"
    try:
        resp = requests.get(url, timeout=(CONNECT_TIMEOUT_SEC, HEALTH_READ_TIMEOUT_SEC))
        data: Any = None
        if resp.headers.get("content-type", "").startswith("application/json"):
            try:
                data = resp.json()
            except Exception:
                data = None
        # Parse common shapes
        ids: List[str] = []
        if isinstance(data, dict):
            dl = data.get("data")
            if isinstance(dl, list):
                for item in dl:
                    if isinstance(item, str):
                        ids.append(item)
                    elif isinstance(item, dict):
                        mid = item.get("id") or item.get("name")
                        if isinstance(mid, str):
                            ids.append(mid)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    ids.append(item)
                elif isinstance(item, dict):
                    mid = item.get("id") or item.get("name")
                    if isinstance(mid, str):
                        ids.append(mid)
        models_set = set(ids)
    except Exception:
        models_set = set()

    # Update cache
    with _models_cache_lock:
        _models_cache[backend] = (set(models_set), now + timedelta(seconds=MODELS_CACHE_TTL_SECONDS))
        return set(models_set)


def _extract_username_from_system_messages(messages: Any) -> Optional[str]:
    """Scan system role content from messages,
    extract xxx from format "User's name is 「xxx」" (supports various quote types) and return.
    Returns None if not found.
    """
    try:
        if not isinstance(messages, list):
            return None
        # Support various opening/closing quote variations
        # Examples: 「」, 『』, " ", " " , ' '
        pattern = re.compile(r"ユーザーの名前は[「『“\"']([^」』”\"']+)[」』”\"']")
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role != "system":
                continue
            content = msg.get("content")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # Support OpenAI content array format (concatenate text)
                parts: List[str] = []
                for item in content:
                    if isinstance(item, dict):
                        t = item.get("text")
                        if isinstance(t, str):
                            parts.append(t)
                text = "\n".join(parts)
            if not text:
                continue
            m = pattern.search(text)
            if m:
                username = (m.group(1) or "").strip()
                if username:
                    return username
    except Exception:
        return None
    return None


# ------------------------------
# Backend Selection
# ------------------------------

def select_backend_for_request(ip: str) -> Optional[str]:
    # Traditional (non-model-specific) selection. Currently unused, expected to return only fallback.
    return FALLBACK_BACKEND


def _count_model_instances(backend: str, model: str) -> int:
    """Count instances of model name, model name-2, model name-3... on specified backend"""
    models_set = _get_available_models_set(backend)
    count = 0
    # The model name itself
    if model in models_set:
        count += 1
    # Check model name-2, model name-3, ...
    i = 2
    while True:
        candidate = f"{model}-{i}"
        if candidate in models_set:
            count += 1
            i += 1
        else:
            break
    return count


def _get_model_instances_inflight_status(backend: str, model: str) -> Tuple[int, List[str]]:
    """Get inflight status of all model instances on specified backend
    
    Returns:
        (total_inflight, idle_instances): Total inflight count and list of instances with 0 inflight
    """
    models_set = _get_available_models_set(backend)
    total_inflight = 0
    idle_instances = []
    
    # The model name itself
    if model in models_set:
        inflight = INFLIGHT_TRACKER.get(backend, model)
        total_inflight += inflight
        if inflight == 0:
            idle_instances.append(model)
    
    # Check model name-2, model name-3, ...
    i = 2
    while True:
        candidate = f"{model}-{i}"
        if candidate in models_set:
            inflight = INFLIGHT_TRACKER.get(backend, candidate)
            total_inflight += inflight
            if inflight == 0:
                idle_instances.append(candidate)
            i += 1
        else:
            break
    
    return total_inflight, idle_instances


def select_backend_for_model_request(ip: str, model: str) -> Tuple[Optional[str], Optional[str]]:
    return BACKEND_SELECTOR.select(ip, model)


# ------------------------------
# Proxy Utilities
# ------------------------------

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _filter_request_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS and k.lower() != "host"}


def _filtered_response_headers(resp: requests.Response) -> Dict[str, str]:
    excluded = HOP_BY_HOP_HEADERS | {"content-length"}
    return {k: v for k, v in resp.headers.items() if k.lower() not in excluded}


def _build_target_url(base: str) -> str:
    base = base.rstrip("/")
    path = request.full_path if request.query_string else request.path
    if path.startswith("/"):
        return base + path
    return base + "/" + path


def _stream_upstream_response(resp: requests.Response, on_complete) -> Iterable[bytes]:
    try:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                yield chunk
    except GeneratorExit:
        try:
            resp.close()
        finally:
            raise
    except Exception:
        # Ensure upstream closed
        resp.close()
        raise
    finally:
        try:
            on_complete()
        except Exception:
            pass


# ------------------------------
# Routes
# ------------------------------

@app.route("/favicon.ico")
def favicon():
    # Not proxied, return empty response (204 No Content)
    return Response(status=204)

@app.route("/llmhealth", methods=["GET"])  # Not proxied
def llmhealth() -> Response:
    max_util = LOCAL_GPU_MONITOR.get_max()
    status = "busy" if max_util >= 50.0 else "idle"

    return jsonify({
        "status": status,
        "gpu_util_max5s": max_util,
        "window_seconds": WINDOW_SECONDS,
    })


@app.route("/access-log-stats", methods=["GET"])  # Access log statistics
def access_log_stats() -> Response:
    """Get access log statistics for monitoring"""
    stats = ACCESS_LOG_MANAGER.get_stats()
    return jsonify(stats)

@app.route("/llmhealth-snapshot", methods=["GET"])  # JSON for monitor
def llmhealth_snapshot() -> Response:
    # Build local summary
    local_max = LOCAL_GPU_MONITOR.get_max()
    local_status = "busy" if local_max >= 50.0 else "idle"

    health_bases = SERVER_REGISTRY.health_bases()
    metrics_snapshot = BACKEND_MONITOR.snapshot_metrics(health_bases)
    
    backends = []
    for base in health_bases:
        m = metrics_snapshot.get(base)
        state = BACKEND_MONITOR.get_conservative_status(base)
        
        # Get inflight information (using modelurl)
        modelurl = SERVER_REGISTRY.modelurl_by_health_base(base)
        backend_inflight = INFLIGHT_TRACKER._backend_counts.get(modelurl, {}) if modelurl else {}
        total_inflight = sum(backend_inflight.values())
        model_inflight = dict(backend_inflight)
        
        # Get request_max information
        request_max = None
        for name, config in SERVER_CONFIGS.items():
            if config.get("addr") + ":" + str(config.get("health-port")) == base:
                request_max = config.get("request-max")
                break
        
        backends.append({
            "base": base,
            "status": state,
            "last": m,
            "total_inflight": total_inflight,
            "model_inflight": model_inflight,
            "request_max": request_max,
        })

    servers_view = {}
    for name in SERVER_REGISTRY.server_names():
        srv = SERVER_REGISTRY.get_server(name)
        if srv:
            server_info = {
                "health_base": srv.health_base,
                "model_base": srv.model_base,
            }
            if srv.request_max is not None:
                server_info["request_max"] = srv.request_max
            servers_view[name] = server_info
    # Also return model-specific structure (for simple display)
    models_view = {}
    for compiled_pattern, server_names, pattern_str in SERVER_REGISTRY.model_patterns:
        models_view[pattern_str] = list(server_names)

    # Create sticky details snapshot (lock protected)
    STICKY_MANAGER.cleanup()
    with STICKY_MANAGER._lock:
        sticky_items = [
            {
                "key": k,
                "ip": (k.split("|")[0] if "|" in k else k),
                "model": (k.split("|", 1)[1] if "|" in k else None),
                "backend": v[0],
                "updated_at": v[1].isoformat().replace("+00:00", "Z"),
            }
            for k, v in STICKY_MANAGER._map.items()
        ]

    return jsonify({
        "local": {
            "status": local_status,
            "gpu_util_max5s": local_max,
            "window_seconds": WINDOW_SECONDS,
        },
        "backends": backends,
        "servers": servers_view,
        "models": models_view,
        "sticky_count": len(sticky_items),
        "sticky": sticky_items,
        "now": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })


@app.route("/v1/models", methods=["GET"])
def models() -> Response:
    """Aggregate models from all backends and return filtered models excluding those with hyphen numbers"""
    all_models = set()
    
    # Get model list from all backends
    for server_name in SERVER_REGISTRY.server_names():
        model_base = _get_model_base_url(server_name)
        if model_base:
            backend_models = _get_available_models_set(model_base)
            all_models.update(backend_models)
    
    # Filter models with hyphen numbers
    # Pattern: model name-number (e.g., model-2, model-3, model-10)
    filtered_models = []
    for model in all_models:
        # Check hyphen number pattern
        if re.match(r'^.+-\d+$', model):
            continue  # Exclude models with hyphen numbers
        filtered_models.append(model)
    
    # Sort and return
    filtered_models.sort()
    
    return jsonify({
        "object": "list",
        "data": [{"id": model, "object": "model"} for model in filtered_models]
    })


@app.route("/llmhealth-monitor", methods=["GET"])  # HTML monitor page
def llmhealth_monitor() -> Response:
    html = """
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>LLM Health Monitor</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 20px; }
      .status { display: inline-block; padding: 2px 8px; border-radius: 12px; color: #fff; font-weight: 600; }
      .idle { background: #16a34a; }
      .busy { background: #dc2626; }
      .invalid { background: #6b7280; }
      table { border-collapse: collapse; width: 100%; margin-top: 12px; }
      th, td { border: 1px solid #e5e7eb; padding: 8px; text-align: left; }
      th { background: #f3f4f6; }
      .muted { color: #6b7280; font-size: 12px; }
      .header { display:flex; align-items: baseline; gap: 12px; }
      .pill { padding: 2px 8px; border-radius: 9999px; background:#eef2ff; color:#3730a3; font-size:12px; }
      .chart-container { margin: 20px 0; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px; background: #f9fafb; }
      .chart-title { font-size: 16px; font-weight: 600; margin-bottom: 15px; color: #374151; }
      .chart { height: 250px; position: relative; background: white; border-radius: 4px; overflow-x: auto; overflow-y: visible; }
      .bar-chart { display: flex; align-items: end; height: 180px; gap: 4px; padding: 30px 10px 20px 10px; min-width: max-content; }
      .bar { background: linear-gradient(to top, #3b82f6, #60a5fa); border-radius: 2px 2px 0 0; min-height: 4px; position: relative; min-width: 40px; max-width: 80px; }
      .bar:hover { background: linear-gradient(to top, #1d4ed8, #3b82f6); }
      .bar-label { position: absolute; bottom: -35px; left: 50%; transform: translateX(-50%); font-size: 9px; color: #6b7280; white-space: nowrap; text-align: center; width: 100px; }
      .bar-value { position: absolute; top: -30px; left: 50%; transform: translateX(-50%); font-size: 10px; font-weight: 600; color: #374151; background: rgba(255, 255, 255, 0.9); padding: 2px 4px; border-radius: 3px; }
      .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 15px 0; }
      .stat-card { padding: 15px; background: white; border: 1px solid #e5e7eb; border-radius: 8px; }
      .stat-value { font-size: 24px; font-weight: 700; color: #1f2937; }
      .stat-label { font-size: 12px; color: #6b7280; margin-top: 4px; }
    </style>
  </head>
  <body>
    <div class=\"header\">
      <h2>LLM Health Monitor</h2>
      <span id=\"now\" class=\"muted\"></span>
      <span id=\"sticky\" class=\"pill\"></span>
    </div>
    <div>
      <h3>Local GPU</h3>
      <div>Status: <span id=\"local-status\" class=\"status\"></span> | Max GPU (5s): <b id=\"local-util\"></b>%</div>
    </div>
      <div>
        <h3>Backends</h3>
        <table>
          <thead>
            <tr><th>#</th><th>Base</th><th>Status</th><th>Last Util(5s max)</th><th>Total Requests</th><th>Model Requests</th><th>Request Max</th><th>Updated</th></tr>
          </thead>
          <tbody id=\"tbody\"></tbody>
        </table>
      </div>
    <div>
      <h3>Sticky Details</h3>
      <table>
        <thead>
          <tr><th>#</th><th>IP/Ident</th><th>Model</th><th>Backend</th><th>Updated</th></tr>
        </thead>
        <tbody id="sticky-tbody"></tbody>
      </table>
    </div>
    
    <!-- Access Log Section -->
    <div>
      <h3>Access Log (Last 1 Hour)</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value" id="total-requests">0</div>
          <div class="stat-label">Total Requests</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" id="unique-ips">0</div>
          <div class="stat-label">Unique IPs</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" id="unique-models">0</div>
          <div class="stat-label">Unique Models</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" id="unique-usernames">0</div>
          <div class="stat-label">Unique Users</div>
        </div>
      </div>
      
      <div class="chart-container">
        <div class="chart-title">Requests Over Time (1-min intervals)</div>
        <div class="chart">
          <div class="bar-chart" id="time-chart"></div>
        </div>
      </div>
      
      <div class="chart-container">
        <div class="chart-title">Requests by Model</div>
        <div class="chart">
          <div class="bar-chart" id="model-chart"></div>
        </div>
      </div>
      
      <div class="chart-container">
        <div class="chart-title">Requests by IP</div>
        <div class="chart">
          <div class="bar-chart" id="ip-chart"></div>
        </div>
      </div>
    </div>
    
    <script>
      async function refresh(){
        try{
          const r = await fetch('/llmhealth-snapshot', { cache: 'no-store' });
          const j = await r.json();
          document.getElementById('now').textContent = j.now;
          document.getElementById('sticky').textContent = 'sticky: ' + j.sticky_count;
          const ls = document.getElementById('local-status');
          ls.textContent = j.local.status;
          ls.className = 'status ' + j.local.status;
          document.getElementById('local-util').textContent = (j.local.gpu_util_max5s ?? 0).toFixed(0);
          const tbody = document.getElementById('tbody');
          tbody.innerHTML='';
          (j.backends||[]).forEach((b, i)=>{
            const tr = document.createElement('tr');
            const last = b.last || {};
            const util = (last.gpu_util_max5s==null)?'-':Number(last.gpu_util_max5s).toFixed(0)+'%';
            const upd = last.updated_at || '-';
            const totalInflight = b.total_inflight || 0;
            const modelInflight = b.model_inflight || {};
            const requestMax = b.request_max || '-';
            
            // Format model-specific request counts
            const modelRequests = Object.entries(modelInflight)
              .filter(([model, count]) => count > 0)
              .map(([model, count]) => `${model}: ${count}`)
              .join('<br>');
            const modelRequestsDisplay = modelRequests || '-';
            
            tr.innerHTML = `<td>${i+1}</td><td>${b.base}</td><td><span class="status ${b.status}">${b.status}</span></td><td>${util}</td><td><b>${totalInflight}</b></td><td class="muted">${modelRequestsDisplay}</td><td class="muted">${requestMax}</td><td class="muted">${upd}</td>`;
            tbody.appendChild(tr);
          });
          // Draw sticky details
          const stickyTbody = document.getElementById('sticky-tbody');
          if (stickyTbody) {
            stickyTbody.innerHTML = '';
            (j.sticky||[]).forEach((s, i)=>{
              const tr = document.createElement('tr');
              const ip = s.ip || '-';
              const model = s.model || '-';
              const backend = s.backend || '-';
              const updated = s.updated_at || '-';
              tr.innerHTML = `<td>${i+1}</td><td>${ip}</td><td>${model}</td><td>${backend}</td><td class="muted">${updated}</td>`;
              stickyTbody.appendChild(tr);
            });
          }
        }catch(e){
          console.error(e);
        }
      }
      
      async function refreshAccessLogs(){
        try{
          const r = await fetch('/access-log-stats', { cache: 'no-store' });
          const stats = await r.json();
          
          // Update stats
          document.getElementById('total-requests').textContent = stats.total_requests || 0;
          document.getElementById('unique-ips').textContent = stats.unique_ips || 0;
          document.getElementById('unique-models').textContent = stats.unique_models || 0;
          document.getElementById('unique-usernames').textContent = stats.unique_usernames || 0;
          
          // Draw model chart
          drawBarChart('model-chart', stats.model_counts || {});
          
          // Draw IP chart
          drawBarChart('ip-chart', stats.ip_counts || {});
          
          // Draw time series chart
          drawBarChart('time-chart', stats.time_series || {});
          
        }catch(e){
          console.error('Access log refresh error:', e);
        }
      }
      
      function drawBarChart(containerId, data) {
        const container = document.getElementById(containerId);
        container.innerHTML = '';
        
        // --- NEW: adjust alignment for time chart ---
        if (containerId === 'time-chart') {
          container.style.justifyContent = 'flex-end';
        } else {
          container.style.justifyContent = 'flex-start';
        }
        
        let entries = Object.entries(data);
        
        // Custom layout tweaks for time-chart
        if (containerId === 'time-chart') {
          container.parentElement.style.overflowX = 'hidden'; // hide horizontal scroll
          container.style.minWidth = '95%';
        }
        
        // For the time chart, sort chronologically (oldest to newest; right edge is now)
        if (containerId === 'time-chart') {
          const STEP_MS = 60 * 1000; // 1 minute
          const WINDOW_COUNT = 120; // show last 2 hours (120*1min)
          const parsed = Object.fromEntries(entries.map(([k, v]) => [new Date(k).getTime(), v]));
          const times = Object.keys(parsed).map(t => Number(t));
          const now = Date.now();
          const nowAligned = Math.floor(now / STEP_MS) * STEP_MS;
          const startT = nowAligned - WINDOW_COUNT * STEP_MS;

          entries = [];
          for (let t = startT; t <= nowAligned; t += STEP_MS) {
            const val = parsed[t] || 0;
            entries.push([new Date(t).toISOString(), val]);
          }
        } else {
          // For other charts, sort by descending value
          entries = entries.sort((a, b) => b[1] - a[1]);
        }
        
        const maxValue = Math.max(...entries.map(([k, v]) => v), 1);
        
        entries.forEach(([key, value]) => {
          const bar = document.createElement('div');
          bar.className = 'bar';
          bar.style.height = `${(value / maxValue) * 100}%`;
          
          const label = document.createElement('div');
          label.className = 'bar-label';
          
          // For the time chart, shorten time labels (HH:mm)
          if (containerId === 'time-chart') {
            const date = new Date(key);
            const hours = date.getHours().toString().padStart(2, '0');
            const minutes = date.getMinutes().toString().padStart(2, '0');
            label.textContent = `${hours}:${minutes}`;
          } else {
            label.textContent = key; // do not abbreviate
          }
          bar.appendChild(label);
          
          const valueLabel = document.createElement('div');
          valueLabel.className = 'bar-value';
          valueLabel.textContent = value;
          bar.appendChild(valueLabel);
          
          container.appendChild(bar);
        });
      }
      
      refresh();
      refreshAccessLogs();
      setInterval(refresh, 5000);
      setInterval(refreshAccessLogs, 10000);
    </script>
  </body>
</html>
    """
    return Response(html, mimetype="text/html; charset=utf-8")


def ApplyCustomClineGBNF(body: Dict[str, Any]):
    CLINE_GBNF: str = '''root ::= analysis? start final .+
analysis ::= "<|channel|>analysis<|message|>" ( [^<] | "<" [^|] | "<|" [^e] )* "<|end|>"
start ::= "<|start|>assistant"
final ::= "<|channel|>final<|message|>"'''
    body["reasoning_format"] = "auto"
    body["grammar"] = CLINE_GBNF

def ApplyCustomCompletions(body: Dict[str, Any]) -> bool:
    modified: bool = False
    if isinstance(body, dict) and body.get("messages"):
        for message in body.get("messages"):
            if isinstance(message, dict) and message.get("role") == "system":
                contents = message.get("content", [])
                text = ""
                if isinstance(contents, str):
                    text = contents
                elif isinstance(contents, list) and 0 < len(contents):
                    first = contents[0]
                    if isinstance(first, dict):
                        text = first.get("text", "")
                if text.startswith("You are Cline") or text.startswith("You are Roo"):
                    ApplyCustomClineGBNF(body)
                    modified = True
                    break
    return modified

@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def proxy(path: str) -> Response:
    client_ip = _get_client_ip()
    client_ident = client_ip  # Default is IP. Replace with username from system prompt if available
    backend: Optional[str] = None
    selected_model: Optional[str] = None

    # Model-specific routing only for POST /v1/chat/completions
    is_modified_body = False
    is_completions = request.method == "POST" and request.path.rstrip("/") == "/v1/chat/completions"
    if is_completions:
        try:
            body = request.get_json(silent=True) or {}
            m = body.get("model") if isinstance(body, dict) else None
            # Extract username from system role
            username = _extract_username_from_system_messages(body.get("messages")) if isinstance(body, dict) else None
            if isinstance(username, str) and username:
                client_ident = username
            if isinstance(m, str) and m:
                selected_model = m
                backend, selected_instance = select_backend_for_model_request(client_ident, m)
                # Use selected instance if available
                if selected_instance:
                    selected_model = selected_instance
                    body["model"] = selected_model
                    is_modified_body = True
                    print(f"[INFO] selected backend and model: {backend} | {selected_model}")

            if ApplyCustomCompletions(body):
                is_modified_body = True
                
            # Log access for completions requests
            if isinstance(m, str) and m:
                ACCESS_LOG_MANAGER.log_access(
                    ip=client_ip,
                    model=m,
                    username=username
                )
        except Exception:
            backend = backend

    # Fallback for everything else
    if not backend:
        backend = FALLBACK_BACKEND
    if not backend:
        return jsonify({"error": "No backend configured"}), 503

    target_url = _build_target_url(backend)
    upstream_headers = _filter_request_headers(dict(request.headers))

    # Get request data (use updated body when model is changed)
    if is_modified_body and 'body' in locals() and body:
        # Serialize updated body when model is changed
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    else:
        # Use original request data in normal cases
        data = request.get_data() if request.method in {"POST", "PUT", "PATCH"} else None

    # Proxy request to the selected backend with streaming
    # Increment active count just before sending (per backend)
    if selected_model and backend:
        INFLIGHT_TRACKER.inc(backend, selected_model)
    try:
        upstream_resp = requests.request(
            method=request.method,
            url=target_url,
            headers=upstream_headers,
            data=data,
            stream=True,
            allow_redirects=False,
            timeout=UPSTREAM_CONNECT_TIMEOUT_SEC,  # Only connect timeout; stream has no read timeout
        )
        
        # Log response Content-Type (for debugging)
        #content_type = upstream_resp.headers.get('content-type', '')
        #if not content_type.startswith('application/json') and is_completions:
        #    print(f"[WARN] Unexpected content-type for completions: {content_type}, URL: {target_url}", file=sys.stderr)
            
    except Exception as exc:
        # Return 502 when upstream connection fails
        return jsonify({"error": "Upstream request failed", "details": str(exc)}), 502


    if is_completions and selected_model and backend:
        STICKY_MANAGER.update_backend(client_ident, backend, model=selected_model)
        
    def _on_complete() -> None:
        try:
            if selected_model and backend:
                INFLIGHT_TRACKER.dec(backend, selected_model)
        finally:
            if is_completions and selected_model and backend:
                STICKY_MANAGER.update_backend(client_ident, backend, model=selected_model)

    response = Response(
        stream_with_context(_stream_upstream_response(upstream_resp, _on_complete)),
        status=upstream_resp.status_code,
        headers=_filtered_response_headers(upstream_resp),
        direct_passthrough=True,
    )
    return response


# ------------------------------
# Bootstrap background workers
# ------------------------------


def _start_background_threads() -> None:
    # GPU monitor
    LOCAL_GPU_MONITOR.start()

    # Backend polling
    BACKEND_MONITOR.start()


_start_background_threads()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    # threaded=True to enable multi-threaded handling
    app.run(host="0.0.0.0", port="18000", threaded=True, debug=debug)





