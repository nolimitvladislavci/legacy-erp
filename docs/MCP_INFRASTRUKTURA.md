## MCP INFRASTRUKTURA — 05.04.2026.

### Arhitektura (finalna)
- nginx /mcp/ → proxy → 127.0.0.1:8765
- mcp-fina.service → mcp_server.py → port 8765
- fenix-mcp.service → DISABLED (bio duplikat, uzrokovao orphan konflikte)

### Problem koji je riješen
Dva servisa (mcp-fina + fenix-mcp) pokretala isti mcp_server.py na istom portu 8765.
Pri restartu jednog — drugi bi ostao kao orphan i blokirao port.
CC Code i Sonnet bi gubili MCP pristup.

### Trajno rješenje
1. fenix-mcp.service → disabled (ne pokreće se nikad više)
2. mcp-fina.service → jedini servis za port 8765
3. ExecStartPre: `fuser -k 8765/tcp || true` — ubija orphane PRIJE starta
4. KillMode=control-group — čisti SVE child procese pri stopu
5. TimeoutStopSec=10 — ne čeka vječno

### Jedini servis koji treba pratiti
`systemctl status mcp-fina`
`ss -tlnp | grep 8765`

### Ako MCP opet padne
```bash
systemctl restart mcp-fina
# NE: systemctl start fenix-mcp — taj je disabled zauvijek
```
