# Istorija Izrade MOC (Dnevnik Rada)

Ovaj dokument služi kao indeks svih izmena, implementacija i sesija razvoja na projektu **sinhronizuj.me**. Povezuje dnevne beleške i glavnu datoteku istorije razvoja.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [istorija_izrade.md](file:///home/gruya/Projektri/sinhronizuj.me/istorija_izrade.md) – Glavna datoteka istorije projekta.

---

## 📅 Hronološki Pregled Implementacija

### Avgust 2026.

#### [[2026-08-30 - Prevodjenje README na engleski]]
*   **Opis**: Kompletno prevođenje glavne projektne dokumentacije (`README.md`) sa srpskog na engleski jezik, uključujući arhitekturu, tokove podataka, komponente, stack, konfiguraciju i plan razvoja.

### Jun 2026.

#### [[2026-06-23 - Uklanjanje Realnih Modal Testova i Deploy na Produkciju]]
*   **Opis**: Uklanjanje nepravilnih testova iz scratch foldera koji šalju zahteve Modal radnicima, optimizacija brzine test paketa i spajanje izmena na granu main radi pokretanja produkcionog deploy-a.

#### [[2026-06-22 - Kompletiranje Ekrana na Stitch-u]]
*   **Opis**: Generisanje preostala dva ekrana (Studio Editor DAW i Admin Panel) sa premium estetikom i dizajn sistemom Deep Space Studio, te verifikacija svih 5 ekrana na Stitch platformi.

#### [[2026-06-22 - Instalacija Stitch-Skills]]
*   **Opis**: Instalacija zvanične biblioteke Stitch-Skills pluginova (`stitch-design`, `stitch-build`, `stitch-utilities`) u globalnu Antigravity konfiguraciju.

#### [[2026-06-21 - Priprema i kreiranje DESIGN.md za Stitch MCP]]
*   **Opis**: Kreiranje centralnog [DESIGN.md](file:///home/gruya/Projektri/sinhronizuj.me/DESIGN.md) sa dizajnerskim smernicama za 5 ekrana, u pripremi za automatsko postavljanje UI/UX na Stitch platformu.

#### [[2026-06-21 - Konfiguracija Stitch MCP-a]]
*   **Opis**: Konfigurisanje Google-ovog Stitch MCP servera sa SSE endpoint-om i X-Goog-Api-Key zaglavljem u mcp_config.json klijenta.

#### [[2026-06-21 - Implementacija Perpetual Learning System-a i Optimizacija Performansi Prevođenja]]
*   **Opis**: Refaktorisana je arhitektura prevođenja i implementiran je trostepeni sistem kontinuiranog učenja (Perpetual Learning System): Real-time TM (Subagent Alpha), Dnevni Pattern Miner (Subagent Beta) i Nedeljni LoRA Fine-Tuner (Subagent Gamma).
*   **Performanse**: Uvećan `batch_size` na 25 rečenica, Lektor early exit, paralelizacija (chunking) i vLLM APC.
*   **Optimizacije**: Definitivno rešenje za NumPy JSON serijalizaciju (monkey-patch na nivou importovanja).

#### [[2026-06-21 - CI-CD Popravke i GHCR Usklađivanje]]
*   **Opis**: Rešavanje Bandit SAST grešaka, dodavanje `.env` interpolacije za docker-compose na staging/production VPS-u i ispravke naziva Docker slika za worker i beat servise na GHCR.
*   **Frontend**: Deblokiranje deploy pipeline-a i rešavanje Playwright E2E testova dodavanjem privremenog Vite `.env` fajla.

#### [[2026-06-21 - Hibridni Model Prevođenja]]
*   **Opis**: Implementacija i verifikacija RAG Translation Memory i LLM Wiki pravila. Integracija sentence-level re-segmentacije, multi-turn critique i LLM Judge gating-a.

#### [[2026-06-20 - Poliranje Prevoda i Rešavanje Timeout-a]]
*   **Opis**: Otklanjanje dijalektizama i čišćenje meta-odgovora modela (ti/vi obraćanje). Rešavanje Nginx 504 Gateway Timeout-a povećanjem timeout-a na 600s za dugotrajne TTS zahteve.

---

## ✍️ Pravila Ažuriranja Istorije
Prilikom završetka svake programerske sesije, AI agent mora:
1.  Upisati sažetak u glavnu datoteku [istorija_izrade.md](file:///home/gruya/Projektri/sinhronizuj.me/istorija_izrade.md).
2.  Kreirati novu detaljnu zabelešku u folderu `second_brain/Dnevnik_Rada/` i povezati je ovde pod hronološkim pregledom.
