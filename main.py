import hashlib
import os

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

EMAIL = os.environ.get("EXAM_EMAIL", "25f2004209@ds.study.iitm.ac.in").strip().lower()
DEFAULT_PROTOCOL = "2025-03-26"
SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"]

app = FastAPI()

TOOL = {
    "name": "solve_challenge",
    "description": "Returns the exam challenge response computed from the X-Exam-Challenge request header.",
    "inputSchema": {"type": "object", "properties": {}},
}


def answer(challenge: str) -> str:
    return hashlib.sha256(f"{challenge}:{EMAIL}".encode()).hexdigest()[:16]


def ok(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def err(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle(msg: dict, headers):
    method = msg.get("method")
    id_ = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion")
        version = requested if requested in SUPPORTED else DEFAULT_PROTOCOL
        return ok(id_, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "exam-mcp-server", "version": "1.0.0"},
        })
    if is_notification:
        return None  # notifications/initialized etc.
    if method == "ping":
        return ok(id_, {})
    if method == "tools/list":
        return ok(id_, {"tools": [TOOL]})
    if method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        if name != "solve_challenge":
            return err(id_, -32602, f"Unknown tool: {name}")
        challenge = headers.get("x-exam-challenge")
        if not challenge:
            return ok(id_, {"content": [{"type": "text", "text": "missing X-Exam-Challenge header"}],
                            "isError": True})
        return ok(id_, {"content": [{"type": "text", "text": answer(challenge.strip())}],
                        "isError": False})
    return err(id_, -32601, f"Method not found: {method}")


@app.get("/")
def health():
    return {"status": "ok"}


@app.api_route("/mcp", methods=["POST"])
@app.api_route("/", methods=["POST"])
async def mcp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(err(None, -32700, "Parse error"), status_code=400)

    if isinstance(body, list):
        out = [r for r in (handle(m, request.headers) for m in body) if r is not None]
        return JSONResponse(out) if out else Response(status_code=202)

    res = handle(body, request.headers)
    if res is None:
        return Response(status_code=202)
    return JSONResponse(res)


@app.get("/mcp")
def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})


@app.delete("/mcp")
def mcp_delete():
    return Response(status_code=405, headers={"Allow": "POST"})
