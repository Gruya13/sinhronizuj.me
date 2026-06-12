# 🛠️ DevOps Predlozi za Unapređenje Sistema (sinhronizuj.me)

Ovaj dokument sadrži detaljnu analizu trenutne infrastrukture i DevOps procesa projekta **sinhronizuj.me**, identifikuje potencijalne probleme, uska grla (bottlenecks) i bezbednosne rizike, i daje konkretne, akcione predloge za unapređenje i prelazak na viši produkcioni nivo.

---

## 📋 1. CI/CD Pipeline & Build Proces (GitHub Actions)

### Trenutno Stanje
U datoteci [deploy.yml](file:///home/gruya/Projektri/sinhronizuj.me/.github/workflows/deploy.yml) deployment se vrši SSH povezivanjem na Staging ili Produkciju i pokretanjem sledećih koraka direktno na serveru:
```bash
git checkout <grana>
git pull origin <grana>
cd frontend && npm install && npm run build
docker compose -f infra/hetzner/docker-compose.prod.yml up -d --build
```

### Problemi i Rizici
1. **Opterećenje resursa na VPS-u (CPU/RAM Spike)**: Pokretanje `npm install`, `npm run build` i `docker compose build` na produkcijskom serveru troši ogromnu količinu CPU i memorije (posebno za backend gde pip instalira teške pakete kao što su PyTorch, Demucs itd.). Ovo može uzrokovati pad servera (Out of Memory - OOM) ili stvoriti latenciju za aktivne korisnike platforme tokom deploymenta.
2. **Brzina Deploymenta**: Građenje svega ispočetka na serveru traje dugo (često nekoliko minuta), što produžava vreme nedostupnosti ili nestabilnosti sistema tokom ažuriranja.
3. **Zavisnosti na serveru**: Server mora imati instaliran Node.js, npm i git, kao i konfigurisane SSH ključeve za povlačenje koda sa GitHub-a.

### Predlog Rešenja: Kontejnerizacija Build Faze & Docker Registry
1. **GitHub Container Registry (GHCR)**: Pomeriti celokupan proces izgradnje (build) slika u GitHub Actions. GitHub Actions će izgraditi backend i frontend Docker slike i poslati (push) ih na GHCR.
2. **Multi-stage Dockerfile za Frontend**: Kreirati Dockerfile za frontend koji u prvoj fazi gradi aplikaciju (Node.js), a u drugoj kopira statičke fajlove u ultra-lagani Nginx kontejner.
3. **Brzi Deploy**: Deployment korak na VPS-u se svodi na preuzimanje gotove slike i zamenu kontejnera, što traje manje od 10 sekundi i ne opterećuje procesor servera:
   ```bash
   docker compose -f infra/hetzner/docker-compose.prod.yml pull
   docker compose -f infra/hetzner/docker-compose.prod.yml up -d
   ```

---

## 🐳 2. Optimizacija Docker & Docker Compose Konfiguracije

### Trenutno Stanje
U datoteci [docker-compose.prod.yml](file:///home/gruya/Projektri/sinhronizuj.me/infra/hetzner/docker-compose.prod.yml) servisi su definisani sa fallback vrednostima za lozinke i direktnim build-om.

### Problemi i Rizici
1. **Bezbednosni rizik (Hardkodovane lozinke)**: Prisustvo podrazumevanih lozinki (poput `sinhronizuj_pass_2026`) u fajlu koji se prati na Git-u predstavlja rizik ako repozitorijum ikada postane javan ili bude kompromitovan.
2. **Nedostatak Healthcheck-ova**: Kontejneri poput API-ja i Celery radnika zavise od baze podataka (`db`) i Redis-a. Ako se baza pokreće sporije, aplikativni kontejneri mogu da puknu pri startu jer `depends_on` bez healthcheck-a proverava samo da li je kontejner pokrenut, a ne i da li je spreman da prima konekcije.
3. **Nema Ograničenja Resursa (No Resource Limits)**: Kontejneri nemaju definisane limite za CPU i RAM. Ako dođe do curenja memorije u nekom workeru ili FFmpeg zablokira procesor, to može dovesti do kolapsa celog VPS-a.

### Predlog Rešenja
1. **Striktne Promenljive Okruženja**: Ukloniti sve fallback vrednosti za lozinke iz `docker-compose.prod.yml` i osigurati da se sistem oslanja isključivo na `.env` fajl na serveru.
2. **Dodavanje Healthcheck-a**:
   ```yaml
   db:
     image: postgres:16-alpine
     # ...
     healthcheck:
       test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
       interval: 5s
       timeout: 5s
       retries: 5

   redis:
     image: redis:7-alpine
     # ...
     healthcheck:
       test: ["CMD", "redis-cli", "ping"]
       interval: 5s
       timeout: 5s
       retries: 5
   ```
   A za `api` i `worker-*` servise konfigurisati:
   ```yaml
   depends_on:
     db:
       condition: service_healthy
     redis:
       condition: service_healthy
   ```
3. **Ograničenje resursa**: Definisati limite u Compose fajlu:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 2G
   ```

---

## 💾 3. Strategija Pravljenja Rezervnih Kopija (Backup & Disaster Recovery)

### Trenutno Stanje
U datoteci [backup.py](file:///home/gruya/Projektri/sinhronizuj.me/infra/backup.py) skripta dump-uje bazu, kompresuje fajlove i šalje ih na MinIO skladište preko `settings.MINIO_ENDPOINT`.

### ⚠️ Kritičan Problem (Single Point of Failure)
MinIO servis (`sinhronizuj-minio`) se nalazi u istom Docker Compose okruženju na **istom fizičkom VPS serveru** kao i baza podataka.
* **Problem**: Ukoliko dođe do hardverskog kvara VPS-a, oštećenja diska ili slučajnog brisanja virtuelne mašine, **gubimo i bazu podataka i sve backup arhive**.
* **Problem 2**: Backup obuhvata samo dump baze podataka, ali ne i korisničke sirove i procesirane medije koji se čuvaju na MinIO volumenu na istom disku.

### Predlog Rešenja
1. **Eksterni Backup Storage**: Promeniti destinaciju backup-a u `backup.py` na eksterni, geografski izolovani Cloud storage (npr. AWS S3, Hetzner Storage Box ili Backblaze B2).
2. **Backup Medija**: Konfigurisati periodičnu sinhronizaciju (npr. preko `rclone` ili namenske python skripte) MinIO `uploads` bucketa na eksternu lokaciju, kako korisnici ne bi izgubili svoje video/audio materijale u slučaju katastrofe.

---

## 📊 4. Monitoring, Logovanje i Alerting

### Trenutno Stanje
Logovi se pišu u lokalne fajlove (`backend_server.log`, `worker.log`, `frontend.log`). Ne postoji sistem za praćenje rada aplikacije u realnom vremenu.

### Problemi i Rizici
1. **Slepa tačka za greške**: Ako Celery radnik tiho pukne ili počne da baca greške pri obradi specifičnog formata videa, programeri to neće saznati sve dok korisnici ne prijave problem.
2. **Prepunjavanje diska**: Logovi koji se pišu u lokalne fajlove nemaju konfigurisane limite ili rotaciju na nivou operativnog sistema, što vremenom može popuniti ceo hard disk na VPS-u.
3. **Nema performanse analitike**: Nema uvida u opterećenje CPU-a, zauzeće memorije, mrežni saobraćaj ili status Modal.com API poziva.

### Predlog Rešenja
1. **Sentry Integracija**: Integrisati **Sentry SDK** u FastAPI (`backend/main.py`) i Celery radnike. Sentry automatski presreće sve greške (500 internal server error) i šalje detaljne izveštaje sa stack-trace-om na email/Slack/Discord.
2. **Spoljni Uptime Monitor**: Postaviti besplatnu instancu **Uptime Kuma** (ili koristiti spoljne servise poput Better Stack / UptimeRobot) koja će svake minute testirati `/health` rutu na API-ju i slati notifikacije u slučaju nedostupnosti.
3. **Docker Log Rotacija**: Definisati rotaciju logova na nivou Docker-a u `/etc/docker/daemon.json` or direktno u `docker-compose.prod.yml`:
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

---

## 🚀 5. Skaliranje i Upravljanje Celery Radnicima

### Trenutno Stanje
U `docker-compose.prod.yml` definisana su tri Celery servisa sa fiksnom konkurencijom (`--concurrency=2`):
* `worker-analyzer` (red: `analyze_queue`)
* `worker-renderer` (red: `render_queue`)
* `worker-default` (red: `default_queue`)

### Analiza i Predlozi
1. **CPU Graničnik**: Lokalne operacije poput preuzimanja videa preko `yt-dlp` i procesiranja zvuka/videa preko FFmpeg-a su CPU-intenzivne. Tri pokrenuta radnika sa po 2 procesa (ukupno 6 paralelnih procesa) mogu lako dovesti CPU VPS-a do 100% iskorišćenosti ako više korisnika paralelno pokrene render.
2. **Predlog**:
   * Ograničiti konkurenciju na slabijim VPS serverima (npr. na 1 po radniku) kako bi se osigurala responzivnost API servera.
   * Premestiti teške FFmpeg operacije u Modal serverless okruženje gde je to moguće, ili obezbediti auto-scaling radnika pokretanjem Celery-ja na zasebnim, namenskim "radničkim" VPS instancama u Hetzneru koje se povezuju na centralni Redis na primarnom serveru.

---

## 🔒 6. Bezbednosne Preporuke za Mrežu (Security & Firewall)

1. **Zatvaranje Portova**: U `docker-compose.prod.yml` su izloženi portovi baze (`5432:5432`), Redis-a (`6379:6379`) i MinIO konzole (`9000:9000`, `9001:9001`) direktno na javni internet.
   * **Rizik**: Iako su zaštićeni lozinkama, izlaganje baze podataka i Redis-a direktno javnom saobraćaju otvara vrata za brute-force napade i skeniranje ranjivosti.
   * **Rešenje**: Ukloniti `ports` sekcije za `db` i `redis` iz produkcionog compose fajla. Pošto su svi servisi u istoj Docker mreži (`sinhronizuj-net`), API i Celery mogu nesmetano komunicirati sa njima koristeći imena servisa (`db:5432`, `redis:6379`), bez potrebe da ti portovi budu vidljivi spoljnom svetu. MinIO portove treba izložiti samo interno ili iza Nginx reverse proxy-ja sa SSL-om.
2. **UFW (Uncomplicated Firewall)**: Na VPS-u omogućiti samo portove `80` (HTTP), `443` (HTTPS) i `22` (SSH za odabrane IP adrese). Sve ostale portove blokirati.
