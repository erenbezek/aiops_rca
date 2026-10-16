"""Generates tests/fixtures/leakage/*.jsonl (collector file exporter format: one OTLP JSON request per line).

Kullanım: python tools/gen_leakage_fixtures.py <çıktı klasörü>
Sahte dosyalar upstream koddan tahmin; değişiklik .jsonl dosyalarında değil burada yapılır, sonra yeniden üretilir.
"""
import itertools
import json
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

_ids = itertools.count(1)
T0 = 1760522400000000000  # 2025-10-15T10:00:00Z, ns


def hexid(width):
    return format(next(_ids) * 7919, f"0{width}x")


def val(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": v}


def attrs(d):
    return [{"key": k, "value": val(v)} for k, v in d.items()]


def resource(service=None, **extra):
    d = {}
    if service is not None:
        d["service.name"] = service
        d["service.namespace"] = "opentelemetry-demo"
    d.update(extra)
    return {"attributes": attrs(d)}


def span(name, a=None, events=None, status=None, kind=2, dur_ms=12):
    s = {
        "traceId": hexid(32),
        "spanId": hexid(16),
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(T0),
        "endTimeUnixNano": str(T0 + dur_ms * 1_000_000),
        "attributes": attrs(a or {}),
        "status": status or {},
    }
    if events:
        s["events"] = [
            {"timeUnixNano": str(T0 + 1000), "name": n, "attributes": attrs(ea)} for n, ea in events
        ]
    return s


def spans_req(service, spans, scope="opentelemetry-demo", **res):
    return {
        "resourceSpans": [
            {"resource": resource(service, **res), "scopeSpans": [{"scope": {"name": scope}, "spans": spans}]}
        ]
    }


def log(body, a=None, severity="INFO"):
    num = {"INFO": 9, "WARN": 13, "ERROR": 17}[severity]
    return {
        "timeUnixNano": str(T0),
        "observedTimeUnixNano": str(T0),
        "severityNumber": num,
        "severityText": severity,
        "body": {"stringValue": body},
        "attributes": attrs(a or {}),
        "traceId": hexid(32),
        "spanId": hexid(16),
    }


def logs_req(service, records, scope="opentelemetry-demo"):
    return {
        "resourceLogs": [
            {"resource": resource(service), "scopeLogs": [{"scope": {"name": scope}, "logRecords": records}]}
        ]
    }


def sum_metric(name, points, unit="1"):
    return {
        "name": name,
        "unit": unit,
        "sum": {
            "dataPoints": [
                {"attributes": attrs(a), "startTimeUnixNano": str(T0), "timeUnixNano": str(T0 + 10**10), "asInt": str(v)}
                for a, v in points
            ],
            "aggregationTemporality": 2,
            "isMonotonic": True,
        },
    }


def gauge_metric(name, value, unit="1"):
    return {
        "name": name,
        "unit": unit,
        "gauge": {"dataPoints": [{"timeUnixNano": str(T0), "asDouble": value}]},
    }


def metrics_req(res, metrics, scope="opentelemetry-demo"):
    return {"resourceMetrics": [{"resource": res, "scopeMetrics": [{"scope": {"name": scope}, "metrics": metrics}]}]}


def envoy(method, path, code, flags, cluster, upstream="172.18.0.10:8080", duration=12):
    # envoy.tmpl.yaml (3.1.0) access log body format
    return (
        f'[2026-10-15T10:00:00.123Z] "{method} {path} HTTP/1.1" {code} {flags} via_upstream - "-" '
        f'0 1532 {duration} {max(duration - 1, 0)} "-" "python-requests/2.32.3" "5f1c2a9e-7b4d-4e1a-9c3f-2d8b6a1e0f47" '
        f'"frontend-proxy:8080" "{upstream}" {cluster} 172.18.0.5:43210 172.18.0.5:8080 172.18.0.21:51234 - -'
    )


def proxy_log(body, path, cluster):
    return log(
        body,
        {
            "event.name": "proxy.access",
            "upstream.cluster": cluster,
            "url.path": path,
            "user_agent.original": "python-requests/2.32.3",
        },
    )


CLEAN_TRAFFIC = spans_req(
    "frontend",
    [span("GET /api/products", {"http.request.method": "GET", "url.path": "/api/products", "http.response.status_code": 200})],
)


def write(name, lines):
    with open(OUT / name, "w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")


# --- leak fixtures: line 1 clean traffic, leak from line 2 on ---

write("leak_flagd_service.jsonl", [
    CLEAN_TRAFFIC,
    spans_req("flagd", [span("flagd.evaluation.v1.Service/ResolveBoolean", {"rpc.system": "grpc"}, kind=2)]),
    logs_req("flagd-ui", [log("POST /api/write 200 in 4ms")]),
])

write("leak_tracing_hook_event.jsonl", [
    CLEAN_TRAFFIC,
    spans_req("checkout", [span(
        "oteldemo.CheckoutService/PlaceOrder",
        {"rpc.system": "grpc", "app.user.currency": "USD"},
        events=[("feature_flag.evaluation", {
            "feature_flag.key": "paymentUnreachable",
            "feature_flag.provider.name": "flagd",
            "feature_flag.result.variant": "on",
        })],
    )]),
])

write("leak_metrics_hook.jsonl", [
    CLEAN_TRAFFIC,
    metrics_req(resource("cart"), [sum_metric("feature_flag.evaluation_success_total", [
        ({"feature_flag.key": "cartFailure", "feature_flag.variant": "on", "feature_flag.provider_name": "flagd"}, 42),
    ])]),
])

write("leak_recommendation_cache_attr.jsonl", [
    CLEAN_TRAFFIC,
    spans_req("recommendation", [span(
        "get_product_list",
        {"app.products.count": 10, "demo.feature_flag.recommendation_cache": True},
    )]),
])

write("leak_ad_log.jsonl", [
    CLEAN_TRAFFIC,
    logs_req("ad", [log("Feature Flag adManualGc enabled, performing a manual gc now")]),
])

write("leak_shipping_log.jsonl", [
    CLEAN_TRAFFIC,
    logs_req("shipping", [
        log("shipping.feature_flag.evaluated"),
        log("Delaying quote by 5s due to intlShippingSlowdown feature flag", severity="WARN"),
    ]),
])

write("leak_envoy_feature_write.jsonl", [
    CLEAN_TRAFFIC,
    logs_req("frontend-proxy", [proxy_log(
        envoy("POST", "/feature/api/write", 200, "-", "flagd-ui", "172.18.0.30:4000"), "/feature/api/write", "flagd-ui"
    )]),
    spans_req("frontend-proxy", [span(
        "ingress",
        {"http.method": "POST", "http.url": "http://frontend-proxy:8080/feature/api/write", "http.status_code": "200"},
    )], scope="envoy"),
])

write("leak_envoy_fault_flag.jsonl", [
    CLEAN_TRAFFIC,
    logs_req("frontend-proxy", [proxy_log(
        envoy("GET", "/images/products/SolarFilter.jpg", 200, "DI", "image-provider", duration=5004),
        "/images/products/SolarFilter.jpg", "image-provider",
    )]),
    logs_req("frontend-proxy", [proxy_log(
        envoy("GET", "/images/products/Telescope.jpg", 504, "DI,UT", "image-provider", duration=10001),
        "/images/products/Telescope.jpg", "image-provider",
    )]),
])

write("leak_envoy_fault_flag_unparsed.jsonl", [
    CLEAN_TRAFFIC,
    logs_req("frontend-proxy", [proxy_log(
        "GET /images/products/SolarFilter.jpg 200 DI,UF 5004ms upstream=image-provider",
        "/images/products/SolarFilter.jpg", "image-provider",
    )]),
])

write("leak_flagservice_route.jsonl", [
    CLEAN_TRAFFIC,
    logs_req("frontend-proxy", [proxy_log(
        envoy("POST", "/flagservice/flagd.evaluation.v1.Service/ResolveBoolean", 200, "-", "flagservice", "172.18.0.31:8013"),
        "/flagservice/flagd.evaluation.v1.Service/ResolveBoolean", "flagservice",
    )]),
    spans_req("load-generator", [span(
        "POST",
        {"http.request.method": "POST", "url.full": "http://flagd:8016/ofrep/v1/evaluate/flags/loadGeneratorFloodHomepage"},
        kind=3,
    )]),
])

write("leak_container_metrics.jsonl", [
    CLEAN_TRAFFIC,
    metrics_req({"attributes": attrs({"container.name": "load-generator", "container.id": "a1b2c3d4e5f6"})},
                [gauge_metric("container.cpu.utilization", 0.87)], scope="dockerstatsreceiver"),
    metrics_req({"attributes": attrs({"container.name": "/load-generator", "container.id": "a1b2c3d4e5f6"})},
                [gauge_metric("container.memory.percent", 41.5)], scope="dockerstatsreceiver"),
    metrics_req(resource("load-generator"),
                [sum_metric("traces.span.metrics.calls", [({"span.name": "GET /", "span.kind": "SPAN_KIND_CLIENT"}, 512)])],
                scope="spanmetricsconnector"),
])

write("leak_product_catalog_status.jsonl", [
    CLEAN_TRAFFIC,
    spans_req("product-catalog", [span(
        "oteldemo.ProductCatalogService/GetProduct",
        {"rpc.system": "grpc", "app.product.id": "OLJCESPC7Z"},
        events=[("exception", {"exception.message": "Error: Product Catalog Fail Feature Flag Enabled"})],
        status={"code": 2, "message": "Error: Product Catalog Fail Feature Flag Enabled"},
    )]),
])

write("leak_lock_contention_log.jsonl", [
    CLEAN_TRAFFIC,
    logs_req("product-catalog", [log(
        "lock contention scenario active: holding ACCESS EXCLUSIVE lock on catalog.products", severity="WARN"
    )]),
])

write("leak_load_generator.jsonl", [
    CLEAN_TRAFFIC,
    spans_req("load-generator", [span("user_flood_home", {"demo.request.flood.count": 50})]),
    logs_req("load-generator", [log("User flooding homepage 50 times")]),
])

# --- clean fixtures ---

PAYMENT_ERR = "Payment request failed. Invalid token. app.loyalty.level=gold"

write("clean_symptoms.jsonl", [
    CLEAN_TRAFFIC,
    spans_req("checkout", [span(
        "oteldemo.CheckoutService/PlaceOrder",
        {"rpc.system": "grpc", "app.user.currency": "USD"},
        events=[("exception", {"exception.message": f"rpc error: code = Unknown desc = {PAYMENT_ERR}"})],
        status={"code": 2, "message": f"failed to charge card: could not charge the card: rpc error: code = Unknown desc = {PAYMENT_ERR}"},
    )]),
    logs_req("payment", [log(PAYMENT_ERR, {"app.loyalty.level": "gold"}, severity="ERROR")]),
    logs_req("recommendation", [log("cache miss for product ids: OLJCESPC7Z, 66VCHSJNUP, 1YMWWN1N4O")]),
    spans_req("ad", [span("oteldemo.AdService/GetAds", {"rpc.system": "grpc", "rpc.grpc.status_code": 14},
                          status={"code": 2, "message": "UNAVAILABLE"})]),
    spans_req("shipping", [span("get-quote", {"app.shipping.zip_code": "94043", "app.shipping.cost.total": 8.99}, dur_ms=5012)]),
    metrics_req(resource("frontend"), [sum_metric("http.server.request.count", [
        ({"http.request.method": "GET", "http.response.status_code": 500, "http.route": "/api/checkout"}, 17),
    ])]),
    metrics_req({"attributes": attrs({"container.name": "checkout", "container.id": "0f9e8d7c6b5a"})},
                [gauge_metric("container.cpu.utilization", 0.12)], scope="dockerstatsreceiver"),
    logs_req("frontend-proxy", [proxy_log(
        envoy("GET", "/api/recommendations?productIds=OLJCESPC7Z", 200, "-", "frontend"),
        "/api/recommendations", "frontend",
    )]),
    logs_req("checkout", [log("failed to send order confirmation: rpc error: code = Unavailable", severity="WARN")]),
    logs_req("product-catalog", [log("slow query (2310 ms): SELECT id, name FROM catalog.products WHERE id = $1", severity="WARN")]),
])

write("clean_false_alarms.jsonl", [
    CLEAN_TRAFFIC,
    # Envoy's other response flags
    logs_req("frontend-proxy", [proxy_log(envoy("GET", "/api/cart", 503, "UF", "frontend"), "/api/cart", "frontend")]),
    logs_req("frontend-proxy", [proxy_log(envoy("GET", "/api/cart", 503, "UF,URX", "frontend"), "/api/cart", "frontend")]),
    # DI elsewhere in an Envoy line (not in the flags field)
    logs_req("frontend-proxy", [proxy_log(
        envoy("GET", "/api/cart?ref=DI&code=DISCOUNT", 200, "-", "frontend"), "/api/cart", "frontend"
    )]),
    # DI inside words in a non-Envoy frontend-proxy log (fallback must stay quiet)
    logs_req("frontend-proxy", [log("Applied DISCOUNT code SUMMER10; DIAG upstream ok")]),
    # features / featured paths
    logs_req("frontend-proxy", [proxy_log(
        envoy("GET", "/api/products/featured", 200, "-", "frontend"), "/api/products/featured", "frontend"
    )]),
    spans_req("frontend", [span("GET /features", {"url.path": "/features", "http.response.status_code": 404})]),
    # real symptom messages
    logs_req("checkout", [
        log("payment failed: card declined", severity="ERROR"),
        log("Payment failure for order 7f3a, retrying", severity="WARN"),
        log("cart failure rate above threshold", severity="WARN"),
    ]),
    # flag-name substrings inside other words
    spans_req("frontend", [span("upload", {"error.type": "upload_failure", "app.reason": "UPLOAD_FAILURE", "app.event": "imageReloadFailure"})]),
])

print("ok", sorted(p.name for p in OUT.iterdir()))
