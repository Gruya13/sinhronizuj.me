# Plan za sutra: Daca Dub v1.5 "Dashboard & Granularity"

Cilj za sutra je da pretvorimo "crnu kutiju" obrade u transparentan dashboard gde korisnik vidi svaku rečenicu u realnom vremenu.

### 1. Granularni Progres (Frontend)
- **Problem:** Trenutno korisnik vidi "Glas generisan" i čeka 15 minuta dok se sve završi.
- **Rešenje:** Implementirati slanje metadata informacija iz Celery-ja nakon svakog uspešno sintetizovanog segmenta.
- **Vizualizacija:** `[██████░░░░] 64 / 149 segmenta sintetizovano`.
- **Vremensko praćenje:** Dodati tajmer koji pokazuje proteklo vreme (`00:12:45`) i procenjeno vreme do kraja (`ETA: 00:08:20`) na osnovu prosečne brzine obrade segmenta.

### 2. Auto-Retry Mehanizam (TTS Engine)
- **Problem:** Ako jedan segment dobije Timeout, trenutno on propada i ostaje tišina.
- **Rešenje:** Implementirati `retry` logiku unutar `synthesize_audio`. Ako port 8080 vrati grešku, isti tekst se automatski šalje na 8081 ili 8082 pre nego što se proglasi neuspeh.

### 3. Dinamičko Povećanje Broja Instanci
- Testirati da li možemo podići **4 instance** Fish API-ja na 24GB VRAM-a uz istovremeni rad Ollama modela.

### 4. UI/UX Poliranje
- Dodati animaciju za "Lektor" fazu (npr. lupu koja prolazi preko teksta).
- Implementirati automatski `localStorage.clear()` ako task ID više nije validan na serveru.
