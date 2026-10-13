"""
interceptor.py - The Intelligence Proxy
Runs on port 8080.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import time
import random
import httpx

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from metric_engine import metric_engine, RequestRecord
from baseline_learner import baseline_learner
from anomaly_detector import anomaly_detector
from correlator import correlator
from severity_scorer import severity_scorer
from ws_broadcaster import broadcaster
from database import (init_db, insert_packet, insert_metric, insert_anomaly,
                      get_recent_packets, get_recent_anomalies)

app = FastAPI(title="Intelligence Proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_ROUTES = {
    "/auth":      "http://localhost:9001",
    "/payments":  "http://localhost:9002",
    "/inventory": "http://localhost:9003",
}

_packet_counter = 0
_start_time = time.time()


def _make_packet_record(endpoint, method, status_code, latency_ms, req_size, resp_size):
    global _packet_counter
    _packet_counter += 1
    if status_code == 0:
        tcp_flags = "RST"
    elif status_code >= 500:
        tcp_flags = "PSH,ACK,RST"
    elif status_code >= 400:
        tcp_flags = "PSH,ACK"
    else:
        tcp_flags = "PSH,ACK"
    src_port = random.randint(49152, 65535)
    dst_port_map = {"/auth": 9001, "/payments": 9002, "/inventory": 9003}
    dst_port = next((v for k, v in dst_port_map.items() if endpoint.startswith(k)), 8080)
    seq = random.randint(1000000, 4000000000)
    return {
        "packet_id": _packet_counter, "timestamp": time.time(),
        "endpoint": endpoint, "method": method, "status_code": status_code,
        "latency_ms": round(latency_ms, 2), "req_size": req_size, "resp_size": resp_size,
        "tcp_flags": tcp_flags, "src_ip": "127.0.0.1", "dst_ip": "127.0.0.1",
        "src_port": src_port, "dst_port": dst_port, "seq_num": seq, "ack_num": seq + req_size + 1,
        "protocol": "TCP/HTTP", "ttl": 64, "window_size": 65535, "ip_version": 4,
    }


async def _run_pipeline(endpoint, anomaly_events):
    correlation = None
    if anomaly_events:
        for event in anomaly_events:
            correlator.record_anomaly(endpoint, event.timestamp)
        correlation = correlator.correlate(endpoint)
    broadcaster.emit_graph(correlator.get_graph_data())
    affected_count = len(correlation.affected_apis) if correlation else (1 if anomaly_events else 0)
    severity_report = severity_scorer.compute(anomaly_events, correlation, affected_count)
    broadcaster.emit_severity(severity_report.to_dict())
    for event in anomaly_events:
        if correlation:
            event.correlated_apis = correlation.affected_apis
        broadcaster.emit_anomaly(event.to_dict())
        await insert_anomaly(event.to_dict())
    if correlation and anomaly_events:
        broadcaster.emit_correlation({
            "root_cause": correlation.root_cause,
            "affected_apis": correlation.affected_apis,
            "propagation_path": correlation.propagation_path,
            "confidence": correlation.confidence,
            "description": correlation.description,
        })


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await broadcaster.connect(ws)
    await broadcaster.broadcast("system", {
        "status": "connected",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "baselines": baseline_learner.get_summary(),
        "graph": correlator.get_graph_data(),
        "severity": severity_scorer.get_current_score(),
        "message": "Intelligence Proxy connected. Monitoring active."
    })
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(ws)


@app.get("/api/status")
async def api_status():
    return {
        "status": "running",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "packets_captured": _packet_counter,
        "endpoints_monitored": metric_engine.get_all_endpoints(),
        "baseline_summary": baseline_learner.get_summary(),
        "current_severity": severity_scorer.get_current_score(),
    }

@app.get("/api/baselines")
async def api_baselines():
    return baseline_learner.get_summary()

@app.get("/api/anomalies")
async def api_anomalies():
    return {"anomalies": await get_recent_anomalies(50)}

@app.get("/api/graph")
async def api_graph():
    return correlator.get_graph_data()

@app.get("/api/severity")
async def api_severity():
    return {"score": severity_scorer.get_current_score(), "history": severity_scorer.get_history()[-50:]}

@app.get("/api/packets")
async def api_packets():
    return {"packets": await get_recent_packets(100)}

@app.post("/api/reset")
async def api_reset():
    global _packet_counter
    _packet_counter = 0
    return {"message": "State reset."}

@app.post("/api/sniffer_batch")
async def sniffer_batch(request: Request):
    """Receives real-world packets from bonus/live_sniffer.py and broadcasts to dashboard."""
    data = await request.json()
    packets = data.get("packets", [])
    for pkt in packets:
        broadcaster.emit_sniffer(pkt)
    return {"received": len(packets)}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    full_path = "/" + path

    if not any(full_path.startswith(p) for p in ["/auth", "/payments", "/inventory"]):
        return JSONResponse({"error": f"No route for {full_path}"}, status_code=404)

    target_base = None
    endpoint_key = None
    for prefix, base in API_ROUTES.items():
        if full_path.startswith(prefix):
            target_base = base
            endpoint_key = prefix
            break

    body = await request.body()
    req_size = len(body)
    headers = dict(request.headers)
    headers.pop("host", None)

    start_ts = time.time()
    status_code = 0
    resp_size = 0
    response_body = b""
    content_type = "application/json"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_base + full_path,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
        status_code = resp.status_code
        response_body = resp.content
        resp_size = len(response_body)
        content_type = resp.headers.get("content-type", "application/json")
        latency_ms = (time.time() - start_ts) * 1000

    except httpx.TimeoutException:
        latency_ms = (time.time() - start_ts) * 1000
        status_code = 504
        response_body = b'{"error":"Gateway timeout"}'
        resp_size = len(response_body)
        metric_engine.record_timeout(endpoint_key)

    except httpx.ConnectError:
        latency_ms = (time.time() - start_ts) * 1000
        status_code = 503
        response_body = b'{"error":"Service unavailable"}'
        resp_size = len(response_body)

    packet = _make_packet_record(full_path, request.method, status_code, latency_ms, req_size, resp_size)
    broadcaster.emit_packet(packet)
    asyncio.create_task(insert_packet(packet))

    rec = RequestRecord(
        timestamp=start_ts, endpoint=endpoint_key, method=request.method,
        status_code=status_code, latency_ms=latency_ms, req_size=req_size,
        resp_size=resp_size,
        client_key=f"{request.client.host}:{request.client.port}" if request.client else "unknown",
    )
    metric_engine.record(rec)

    metrics = metric_engine.compute(endpoint_key)
    if metrics:
        metrics_dict = {
            "latency_ms": metrics.latency_ms, "error_rate": metrics.error_rate,
            "packet_loss": metrics.packet_loss, "throughput_rps": metrics.throughput_rps,
            "avg_payload": metrics.avg_payload, "retry_count": metrics.retry_count,
        }
        baseline_learner.update(endpoint_key, metrics_dict)
        baselines = baseline_learner.get_all_baselines(endpoint_key)
        broadcaster.emit_metrics({
            "endpoint": endpoint_key, "metrics": metrics_dict,
            "baselines": baselines, "sample_count": metrics.sample_count,
            "baseline_ready": baseline_learner.is_ready(endpoint_key),
        })
        asyncio.create_task(insert_metric({
            **metrics_dict, "endpoint": endpoint_key,
            "baseline_lat": baselines.get("latency_ms", {}).get("baseline", 0),
            "baseline_upper": baselines.get("latency_ms", {}).get("upper_band", 0),
            "baseline_lower": baselines.get("latency_ms", {}).get("lower_band", 0),
        }))
        anomaly_events = anomaly_detector.detect(endpoint_key, metrics_dict)
        asyncio.create_task(_run_pipeline(endpoint_key, anomaly_events))

    return Response(content=response_body, status_code=status_code, media_type=content_type)


@app.on_event("startup")
async def startup():
    await init_db()
    broadcaster.set_loop(asyncio.get_event_loop())
    print("[Proxy] Intelligence Proxy started on port 8080")
    print("[Proxy] WebSocket: ws://localhost:8080/ws")

    async def heartbeat():
        while True:
            await asyncio.sleep(2)
            broadcaster.emit_system({
                "status": "running",
                "uptime_seconds": round(time.time() - _start_time, 1),
                "packets_captured": _packet_counter,
                "severity": severity_scorer.get_current_score(),
                "baselines_ready": {ep: baseline_learner.is_ready(ep) for ep in metric_engine.get_all_endpoints()}
            })
    asyncio.create_task(heartbeat())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
