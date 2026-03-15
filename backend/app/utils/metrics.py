from prometheus_client import Counter, Histogram, Gauge

# Webhook Layer
webhook_requests_total = Counter(
    "webhook_requests_total",
    "Total webhook requests received",
    ["symbol"]
)

webhook_latency_seconds = Histogram(
    "webhook_latency_seconds",
    "Time spent processing webhook logic",
    ["symbol"]
)

webhook_errors_total = Counter(
    "webhook_errors_total",
    "Total webhook verification or processing errors",
    ["error_type"]
)

# Signal Router Layer
signals_received_total = Counter(
    "signals_received_total",
    "Total signals parsed by the router",
    ["bot"]
)

signals_routed_total = Counter(
    "signals_routed_total",
    "Total individual user trades fanned out to Redis",
    ["bot"]
)

signals_dropped_total = Counter(
    "signals_dropped_total",
    "Total signals dropped (e.g. inactive bot, unprovisioned user)",
    ["reason"]
)

idempotency_drops_total = Counter(
    "idempotency_drops_total",
    "Total signals dropped due to Redis idempotency hash match",
    ["bot"]
)

# Worker & Queue Layer
signals_processed_total = Counter(
    "signals_processed_total",
    "Total signals pulled from the queue and processed by the worker",
    ["bot"]
)

worker_processing_latency_seconds = Histogram(
    "worker_processing_latency_seconds",
    "Time spent by the worker to process and execute a single trade signal",
    ["bot"]
)

redis_queue_length = Gauge(
    "redis_queue_length",
    "Number of pending signals sitting in the Redis queue"
)

redis_queue_wait_seconds = Histogram(
    "redis_queue_wait_seconds",
    "Time a signal waited in the Redis queue before being picked up by a worker"
)

# Broker Execution Layer
metaapi_execution_latency = Histogram(
    "metaapi_execution_latency",
    "Time taken for MetaApi to confirm order placement",
    ["symbol"]
)

successful_trades_total = Counter(
    "successful_trades_total",
    "Total successful trades executed via the broker",
    ["symbol"]
)

execution_failures_total = Counter(
    "execution_failures_total",
    "Total trade execution failures (invalid lot, connection dropped, margin)",
    ["reason"]
)

# Risk Engine
risk_guard_triggers_total = Counter(
    "risk_guard_triggers_total",
    "Total times an operational safety guard halted a trade",
    ["type"]  # e.g., 'drawdown', 'rate_limit', 'max_positions', 'broker_disconnected'
)
