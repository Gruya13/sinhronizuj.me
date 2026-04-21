# Vodič: Pokretanje Daca Dub sistema na RunPod On-Demand Serveru

Pošto AI modeli kao što su *Demucs*, *faster-whisper*, *XTTS v2* i *Wav2Lip* konzumiraju mnogo VRAM-a, najbolje i najisplativije rešenje za obradu dugačkih videa bez blokade sopstvenog kompjutera jeste iznajmljivanje **RunPod On-Demand GPU** instanci.

Na RunPodu plaćaš server *samo onoliko vremena koliko je upaljen* (oko 0.20$ do 0.40$ po satu za moćne grafičke).

Evo tačnog, tehničkog plana kako da ovaj GitHub repozitorijum postaviš i podigneš na RunPodu u samo nekoliko klikova.

## Korak 1: Zakup RunPod Instance

1. Registruj se i dodaj malo kredita na [RunPod.io](https://www.runpod.io/).
2. Idi na sekciju **Pods** i klikni na dugme **Deploy**.
3. Izaberi **Secure Cloud** (najstabilnije mašine).
4. Izaberi grafičku karticu. Preporuka za naš Daca Dub (VRAM Optimizovan):
   * **RTX 3090 (24GB VRAM)** - *Najbolji odnos cene i brzine (oko $0.39/h)*.
   * **RTX 4090 (24GB VRAM)** - *Za ultrabrzu obradu*.
   * **RTX A4000 (16GB VRAM)** - *Budget varijanta (oko $0.30/h), savršeno će se uklopiti u naš sekvencijalni model*.
5. **Template (Veoma bitno!)**: Izaberi **RunPod PyTorch 2.1** (ili viši) templejt. Ovaj templejt u startu ima instaliran NVIDIA Docker i sve potrebne drajvere.
6. Konfiguriši Disk: Stavi **Container Disk** na `40 GB`, a **Volume Disk** na `50 GB` (video obrada zauzima mesta).
7. Klikni na **Deploy** i sačekaj minut da server proradi.

## Korak 2: Pristup Serveru (SSH)

1. Kada se server upali (status: *Running*), klikni na dugme **Connect**.
2. Kopiraj SSH komandu (izgledaće nešto kao `ssh root@xx.runpod.io -p 12345`).
3. Otvori terminal na svom Windowsu/Macu/Linuxu i zalepi SSH komandu da uđeš u server.
   *(Alternativno: Možeš kliknuti na `Connect to Web Terminal` iz samog browsera na RunPodu).*

## Korak 3: Postavljanje Daca Dub koda na Server

Kada se nađeš u crnom terminalu RunPod servera (nalaziš se u `/workspace` folderu, koji jedini čuva podatke posle restarta!), kucaj sledeće komande:

```bash
# 1. Kloniraj naš repozitorijum
git clone https://github.com/Gruya13/daca_dub.git

# 2. Udji u folder
cd daca_dub

# 3. Kreiraj .env fajl i unesi Gemini kljuc
nano .env
```

Kada se otvori nano editor, upiši svoj ključ za prevodioca:
```env
GEMINI_API_KEY=TVOJ_GOOGLE_KLJUC
```
Pritisni `CTRL+O` pa `Enter` da sačuvaš, a onda `CTRL+X` da izađeš.

## Korak 4: Podizanje Sistemske Arhitekture (Docker)

Pošto je RunPod već postavio drajvere, sve što mi treba da uradimo je da okinemo Docker Compose koji će skinuti potrebne fajlove i podići Redis, FastAPI i Celery sa NVIDIA integracijom:

```bash
# Komanda za pokretanje sva tri modula u pozadini
docker compose up -d --build
```

Ovo će prvi put trajati par minuta dok ne skine sistemski ffmpeg i instalira Python zahteve.

## Korak 5: Testiranje Sistema

Da bi video da li Worker (Radnik) radi kako treba i kakvi se logovi ispisuju tokom Faza 1-7, uvek možeš pročitati njegove logove komandom:

```bash
docker compose logs -f worker
```
*(Za izlazak iz logova pritisni `CTRL+C`).*

Tvoj Fast API je sada izložen na portu 8000 tog kontejnera. Na platformi RunPod, u delu "Connect", naći ćeš dugme **"HTTP Service"** i port **8000**. Klikom na to otvara ti se tvoj API spolja, odakle možeš započeti sinhronizaciju videa putem POST zahteva.

**NAPOMENA ZA ZAVRŠETAK:** Kada završiš sa obradom videa, skini `final_mix_daca_dub.mp4` iz `temp_workspace` foldera na svoj lični računar. Nakon toga obavezno **STOPIRAJ (Stop Pod)** instancu na RunPodu kako ti ne bi trošila novac dok je ne koristiš!
