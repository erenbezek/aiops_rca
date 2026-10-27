"""quote-gateway: shipping'in fiyat isteğini (POST /getquote, {"numberOfItems": n}) quote'a iletir, cevabı aynen döner.

OTel `opentelemetry-instrument` ile (Flask, requests, loglar); hata açma OpenFeature + flagd, istek başına okunur.
Flag'ler (deploy/otel-demo/flagd-extras.json): yanlış yapılandırma (iletim var olmayan adrese), gecikme (ms),
bellek sızıntısı (istek başına KB). Adlarda, loglarda ve span'lerde hataya ya da flag'e ipucu yok (sızıntı kuralı).
"""
import logging
import os
import time

import requests
from flask import Flask, Response, request
from openfeature import api
from openfeature.contrib.hook.opentelemetry import TracingHook
from openfeature.contrib.provider.flagd import FlagdProvider

from gateway import QuoteCache, parse_items

PORT = int(os.environ.get("QUOTE_GATEWAY_PORT", "8090"))
UPSTREAM = os.environ.get("QUOTE_ADDR", "http://quote:8090")
ALT_UPSTREAM = "http://quote-svc:8090"
TIMEOUT_S = 10

app = Flask(__name__)
cache = QuoteCache()
log = logging.getLogger("quote-gateway")
log.setLevel(logging.INFO)
session = requests.Session()


@app.post("/getquote")
def getquote():
    n = parse_items(request.get_json(silent=True))
    if n is None:
        log.warning("rejected quote request: numberOfItems must be a non-negative integer")
        return Response("numberOfItems must be a non-negative integer", status=400)
    flags = api.get_client()
    target = ALT_UPSTREAM if flags.get_boolean_value("quoteGatewayMisroute", False) else UPSTREAM
    wait_ms = flags.get_integer_value("quoteGatewaySlowdown", 0)
    retain_kb = flags.get_integer_value("quoteGatewayMemoryLeak", 0)
    if wait_ms > 0:
        time.sleep(wait_ms / 1000)
    body = cache.get(n)
    if body is None:
        try:
            r = session.post(f"{target}/getquote", json={"numberOfItems": n}, timeout=TIMEOUT_S)
            r.raise_for_status()
        except requests.RequestException as e:
            log.error("quote upstream request failed: %s", e)
            return Response("quote upstream unavailable", status=502)
        body = r.text
    cache.put(n, body, retain_kb=retain_kb)
    return Response(body, status=200, content_type="application/json")


if __name__ == "__main__":
    api.set_provider(FlagdProvider(host=os.environ.get("FLAGD_HOST", "flagd"),
                                   port=int(os.environ.get("FLAGD_PORT", "8013"))))
    api.add_hooks([TracingHook()])
    app.run(host="0.0.0.0", port=PORT, threaded=True)
