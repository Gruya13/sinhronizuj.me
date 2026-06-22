# Sistem Samounapređenja (Perpetual Learning System)

Ovaj dokument detaljno opisuje trostepeni sistem za automatsko, neprekidno učenje i samounapređenje prevoda na platformi **sinhronizuj.me** na osnovu ručnih ispravki korisnika.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Funkcionalnosti_MOC]]
*   [[Prevodilacki_Pipeline]]
*   [[Baza_Podataka]]

---

## 1. Pregled Arhitekture Samounapređenja

Da bi se prevazišla statičnost tradicionalnih prevodilačkih modela, sinhronizuj.me koristi sistem sa tri nezavisna agenta (Alpha, Beta i Gamma) koji formiraju zatvorenu petlju učenja (Feedback Loop). Sistem analizira ručne izmene korisnika u studiju i automatski prilagođava buduće prevode kroz tri različite brzine reakcije:

| Agent | Vreme reakcije | Tehnologija | Cilj |
| :--- | :--- | :--- | :--- |
| **Alpha (Alfa)** | **Realno vreme** | Celery + RAG (Vector TM) | Odmah poboljšava naredne segmente u istom ili sledećim projektima |
| **Beta** | **Dnevno (Noću)** | DBSCAN + Qwen3-32B | Otkriva sistemske stilske obrasce i generiše predloge za Wiki pravila |
| **Gamma (Gama)** | **Nedeljno** | Modal (Serverless Fine-tuning) | Trenira i učitava novi LoRA adapter bez downtime-a (Hot-Swap) |

---

## 2. Subagent Alpha: Real-time "Tihi Konsenzus"

Alpha agent je zadužen za instantno učenje. Kada korisnik u editoru ručno ispravi prevedene segmente i klikne na čuvanje nacrta, pokreće se grupni (batch) Celery task `learn_user_glossary_batch_task` u [tasks.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/worker/tasks.py) koji procesira sve korekcije odjednom:

1.  **Evaluacija Kvaliteta**: Sistem računa CometKiwi QE score (`qe_score`) ispravljenog segmenta.
2.  **Tihi Konsenzus (Auto-odobrenje)**:
    *   Ukoliko je `qe_score >= 0.88`, sistem automatski prepoznaje ispravku kao visokokvalitetnu.
    *   Upisuje par (original, ispravljeni_prevod) u tabelu `translation_memory` sa oznakom `auto_approved=True`.
    *   Generiše 384-dimenzionalni semantički embedding koji RAG može koristiti već u sledećem batch-u prevođenja.
3.  **Pending Skladište**:
    *   Ukoliko je `qe_score < 0.88`, par se privremeno upisuje u tabelu `pending_translation_memory` kao sumnjiv (kako ne bi zagadio bazu Primera).
4.  **Promocija (Celery Beat)**:
    *   Periodični Celery Beat zadatak `promote_pending_tm_task` pretražuje `pending_translation_memory` bazu i propušta segmente kroz LLM Judge. Ako sudija dodeli ocenu $\ge 4.5/5.0$, segment se promoviše u glavnu `translation_memory` tabelu.

---

## 3. Subagent Beta: Dnevni "Lovac na Obrasce"

Subagent Beta vrši analizu koherentnosti na srednjem vremenskom nivou. Svake noći u 02:00h, Celery Beat pokreće skriptu `backend/worker/translation/pattern_miner.py`.

### 3.1. DBSCAN Klasterovanje
1.  Učitavaju se svi novi zapisi iz `translation_memory` dodati u prethodnih 24 sata za određenog korisnika.
2.  Primenjuje se **DBSCAN** (Density-Based Spatial Clustering of Applications with Noise) algoritam nad embedding-zima rečenica:
    *   `eps=0.35` (maksimalna semantička udaljenost unutar klastera).
    *   `min_samples=3` (klaster se formira ako korisnik napravi najmanje 3 slične izmene).
3.  Sve izolovane izmene (šum) se odbacuju, a zadržavaju se samo sistematska pravila prevođenja.

### 3.2. Formulisanje Wiki Pravila
*   Za svaki uspešno detektovani klaster (npr. prevođenje termina *framework* u *razvojan okvir*), Qwen-32B analizira primere i formuliše precizno lingvističko pravilo u JSON formatu:
    ```json
    {
      "title": "Prevod termina Framework",
      "content": "Termin 'framework' u IT kontekstu uvek prevoditi kao 'razvojni okvir', a ne 'okvir rada'."
    }
    ```
*   Pravilo se dodaje u tabelu `wiki_rules` kao predlog. Korisnik u interfejsu dobija notifikaciju i može da odobri pravilo, nakon čega ono postaje aktivno za sve buduće prevode (Faza 0).

---

## 4. Subagent Gamma: Nedeljni LoRA Fine-Tuner

Na najdubljem nivou, Gamma agent menja same težine modela kroz finotuning na Modalu bez menjanja bazičnog LLM koda.

### 4.1. Priprema Dataset-a (`data_generator.py`)
Jednom nedeljno pokreće se skripta koja:
1.  Učitava sve parove iz `translation_memory` za korisnika.
2.  Filtrira samo one sa najvišim kvalitetom (`qe_score >= 0.90`).
3.  Konvertuje ih u Qwen Chat format (User: originalni EN tekst, Assistant: srpski prevod).
4.  Generiše datoteku `dataset.jsonl` i otprema je na bezbedno skladište.

### 4.2. Modal Serverless Trening (`train_lora.py`)
Trening se obavlja serverless na Modalu kako se ne bi opterećivao host VPS:
1.  Rezerviše se kontejner sa **Nvidia A10G (24GB VRAM)** GPU-om.
2.  Montira se deljeni mrežni NFS volumen `/models` i HuggingFace okruženjska promenljiva `HF_HOME` se postavlja na `/models/huggingface_cache` pre pokretanja treninga. Na ovaj način se preuzeti LLM modeli (poput Qwen 32B) trajno keširaju, što dramatično ubrzava pokretanje serverless instanci i eliminiše mrežne troškove ponovnog preuzimanja modela.
3.  Učitava se baza `dataset.jsonl` i pokreće se trening nad modelom `Qwen/Qwen2-32B-Instruct` (uz AWQ/Marlin kvantizaciju).
4.  LoRA parametri su postavljeni na `r=16` i `lora_alpha=32` i gađaju projekcione matrice (`q_proj`, `v_proj`, `k_proj`, `o_proj`).
5.  Trening se obično vrši u 3 epohe kako bi se izbegao overfitting. Novodobijeni adapter se čuva na Modal shared storage.

---

## 5. Redis Blue-Green Hot-Swap Mehanizam

Da bi se novoobučeni LoRA adapter učitao bez ikakvog zastoja u radu (downtime), koristi se Blue-Green ruter kroz Redis:

```
[Korisnik šalje video na prevod]
           │
           ▼
┌───────────────────────────┐
│     Celery Translator     │
│  (Čita active_lora_key)   │
└──────────┬────────────────┘
           │
           ├──────────► [Redis: active_lora_path = "adapter_blue"]
           │            Poziva vLLM na Modalu sa "adapter_blue"
           │
   (Nakon treninga, Gamma agent postavlja novi adapter)
           │
           ├──────────► [Redis: active_lora_path = "adapter_green"]
           │
           ▼
[Svi sledeći prevodi automatski koriste "adapter_green"]
(Stari adapter "adapter_blue" se bezbedno gasi u pozadini na vLLM-u)
```

Prednosti ovog mehanizma:
*   **0ms downtime**: Nema potrebe za restartovanjem API servera ili vLLM radnika na Modalu.
*   **Automatski Fallback**: U slučaju bilo kakve greške pri učitavanju Green adaptera, Redis ključ se automatski vraća na prethodnu stabilnu verziju (Blue).
