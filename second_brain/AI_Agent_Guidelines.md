# Smernice za AI Agente (AI Agent Guidelines)

Dobrodošao, AI agente! Ovaj projekat koristi **Obsidian Second Brain** (Wiki) sistem za upravljanje znanjem i dokumentovanje rada. Tvoj zadatak je da prilikom rada na ovom projektu aktivno koristiš, pretražuješ i ažuriraš ovaj wiki kako bismo održali maksimalnu konzistentnost koda, arhitekture i dokumentacije.

Ovaj fajl služi kao tvoj primarni sistemski prompt za interakciju sa wiki sistemom.

---

## 1. Zlatna Pravila za AI Agente

1.  **ČITAJ PRE RADA:** Pre nego što započneš rad na bilo kom zadatku (bilo da je to implementacija, popravka greške ili refaktorišući proces), tvoj prvi korak **mora** biti pretraga ovog trezora (`second_brain/`). Pogledaj da li postoji beleška koja opisuje modul na kojem radiš.
2.  **PIŠI NAKON RADA:** Kada završiš implementaciju ili rešiš bag, tvoja je obaveza da ažuriraš postojeće fajlove ili kreiraš novu belešku u odgovarajućem folderu.
3.  **KORISTI DVOSMERNE LINKOVE:** Povezuj beleške koristeći Obsidian sintaksu dvosmernih linkova: `[[Naziv Beleške]]`. Poveži novu belešku sa indeksnim fajlom `[[00_MOC_Index]]` ili odgovarajućim MOC fajlom u podfolderima.
4.  **ISTORIJA IZDRE:** Svaka izmena mora biti zabeležena u fajlu [istorija_izrade.md](file:///home/gruya/Projektri/sinhronizuj.me/istorija_izrade.md) sa tačnim datumom, vremenom i detaljnim opisom šta je urađeno. U toj belešci takođe možeš napraviti link ka novoj wiki belešci.
5.  **JEZIK:** Sva komunikacija sa korisnikom i razmišljanje se odvija na **srpskom jeziku**, a dokumentacija u Wiki-ju se piše na srpskom jeziku (osim tehničkih termina koji se mogu pisati na engleskom ili u originalu).

---

## 2. Struktura Trezora (Vault Structure)

Trezor je podeljen na nekoliko ključnih oblasti:

*   **`00_MOC_Index.md`** – Glavna mapa sadržaja (Map of Content). Odavde počinješ svaku pretragu.
*   📁 **`Arhitektura/`** – Dokumenti koji opisuju celokupnu arhitekturu sistema, bazu podataka, mrežne protokole i tokove podataka.
*   📁 **`Funkcionalnosti/`** – Beleške o pojedinačnim modulima (npr. prevođenje, ASR, TTS, lipsync, frontend, backend).
*   📁 **`Dnevnik_Rada/`** – Dnevni zapisi i istorija izrade. Ovde se nalazi i `[[Istorija_Izrade_MOC]]`.
*   📁 **`Rešavanje_Problema/`** – Zapisani problemi (bagovi), njihove uzročne analize i rešenja, kao i uputstva za podešavanje okruženja.

---

## 3. Kako pretraživati Wiki?

*   Koristi alat `grep_search` za pretragu ključnih reči unutar direktorijuma `second_brain/`.
*   Uvek analiziraj `00_MOC_Index.md` kako bi dobio širu sliku o povezanim konceptima.
*   Ako naiđeš na nejasnoću u kodu (npr. zašto je neka funkcija implementirana na specifičan način), pretraži folder `Rešavanje_Problema/` da vidiš da li je ranije bilo sličnih problema.

---

## 4. Kako kreirati i ažurirati beleške?

Kada kreiraš novu belešku, pridržavaj se sledećeg šablona:

```markdown
# [Naziv Beleške]

Kratak opis čemu služi ova beleška ili modul.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Druga_Povezana_Beleška]]

## Detaljan Opis / Tehnički Detalji
[Unesi detaljan opis, arhitekturu, API rute ili šemu baze]

## Tokovi Podataka (Data Flow)
[Po mogućstvu unesi mermaid dijagram koji objašnjava tok]

## Istorijat Izmena
*   **[[Datum]]**: Opis izmene - [[AI Agent / Korisnik]]
```

### Pravila za linkovanje fajlova koda:
Kada u belešci spominješ fajlove u repozitorijumu, uvek kreiraj apsolutne klikabilne linkove sa protokolom `file:///`. Na primer:
*   Pravilno: `Modeli su definisani u [models.py](file:///home/gruya/Projektri/sinhronizuj.me/backend/core/models.py).`
*   Nepravilno: `Modeli su definisani u backend/core/models.py.`

---

## 5. Integracija sa Gitom i granom `development`

Nakon što implementiraš novu funkcionalnost i korisnik potvrdi da sve radi:
1.  Ažuriraj relevantne delove Wiki-ja.
2.  Upiši izmene u `istorija_izrade.md`.
3.  Uradi Git commit sa jasnom porukom.
4.  Odradi push izmena na granu `development` na GitHubu.
