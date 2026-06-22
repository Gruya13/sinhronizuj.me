# 2026-06-21 - Priprema i kreiranje DESIGN.md za Stitch MCP

Kreiranje centralne dizajnerske specifikacije u pripremi za automatsko postavljanje UI/UX ekrana na Stitch platformu.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Istorija_Izrade_MOC]]
*   [[2026-06-21 - Konfiguracija Stitch MCP-a]]

## Detaljan Opis / Tehnički Detalji
U sklopu pripreme za postavljanje kompletnog korisničkog interfejsa na Google-ov Stitch MCP server, kreirana je datoteka [DESIGN.md](file:///home/gruya/Projektri/sinhronizuj.me/DESIGN.md) u korenu projekta. 

Ova datoteka sadrži sve neophodne informacije za Stitch kako bi se postigao željeni vizuelni stil:
1. **Dizajn tokens (boje, fontovi, prelivi)**: Definisana je tamna tema sa staklenim panelima (glassmorphism), neon akcentima (Cyan, AI Purple, Emerald Green).
2. **Korisničke komponente**: Rotirajući taster (Knob dial), Studio vremenska linija sa dva audio talasa, i kartice za uređivanje segmenata.
3. **Raspored i struktura 5 ekrana**:
   - **Landing Page**: prezentacija i video demo sa dvostrukim player-om.
   - **Login & Waitlist**: centrirana staklena kartica za pristup.
   - **Dashboard**: mrežni status servera, lista projekata i forma za unos.
   - **Studio DAW**: podeljeni ekran (Video player + lista segmenata) sa vremenskom linijom i mikserom zvuka na dnu.
   - **Admin Panel**: waitlist, upravljanje korisnicima i real-time Celery konzola.

## Otvorena Pitanja / Prepreke
*   **Stitch 401 Unauthorized**: Tokom testiranja poziva `list_projects` i `list_design_systems`, Stitch server vraća grešku da API ključ nema validne kredencijale (očekuje OAuth 2 token). Pitanje je prosleđeno korisniku kroz plan implementacije.

## Istorijat Izmena
*   **2026-06-21**: Kreiran `DESIGN.md` i napisan plan implementacije za Stitch MCP.
