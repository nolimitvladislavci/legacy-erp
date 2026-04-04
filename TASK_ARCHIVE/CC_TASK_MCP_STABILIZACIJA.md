# CC_TASK: MCP SSE Stabilizacija — P1

## Problem
MCP SSE pada svaki Gunicorn/Nginx restart jer živi unutar istog procesa.

## Rješenje
Odvojiti MCP na uvicorn :8001, odvojen systemd service.

## Koraci
1. venv/bin/pip install uvicorn
2. Kreirati /etc/systemd/system/mcp-fina.service (uvicorn :8001)
3. Nginx: /mcp/ → :8001 (proxy_buffering off, proxy_read_timeout 86400s)
4. Nginx: / → :8000 (Gunicorn, nepromijenjeno)
5. systemctl enable --now mcp-fina

## Rezultat
Gunicorn restart ne ubija MCP. Zero downtime za Claude.ai.

Status: PENDING — 01.04.2026.
