# 2026-06-21 - Konfiguracija Stitch MCP-a

Povezivanje Stitch MCP servera sa Antigravity klijentom kako bi agent dobio pristup eksternim Google alatima.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Istorija_Izrade_MOC]]

## Detaljan Opis / Tehnički Detalji
Stitch je Google-ov MCP (Model Context Protocol) server koji je integrisan u razvojno okruženje klijenta Antigravity. Konfiguracija je izvršena izmenom datoteke [mcp_config.json](file:///home/gruya/.gemini/antigravity/mcp_config.json).

### Konfiguracioni detalji:
U okviru sekcije `mcpServers` dodat je ključ `stitch` sa sledećom strukturom:
- **`serverUrl`**: `https://stitch.googleapis.com/mcp` (SSE endpoint za komunikaciju sa serverom)
- **`headers`**: Sadrži `X-Goog-Api-Key` koji autorizuje agenta za korišćenje Stitch alata.

Ažurirani [mcp_config.json](file:///home/gruya/.gemini/antigravity/mcp_config.json) fajl:
```json
{
  "mcpServers": {
    "pencil": {
      "command": "/home/gruya/.antigravity/extensions/highagency.pencildev-0.6.50-universal/out/mcp-server-linux-x64",
      "args": [
        "--app",
        "antigravity",
        "--agent",
        "antigravityIDE"
      ],
      "env": {}
    },
    "stitch": {
      "serverUrl": "https://stitch.googleapis.com/mcp",
      "headers": {
        "X-Goog-Api-Key": "YOUR_GCP_API_KEY"
      }
    }
  }
}
```

## Istorijat Izmena
*   **2026-06-21**: Kreirana konfiguracija i povezan Stitch server - Antigravity.
