# 2026-06-22 - Instalacija Stitch-Skills

Instalacija Stitch-Skills biblioteke i odgovarajućih pluginova u globalni konfiguracioni direktorijum Antigravity klijenta kako bi agent imao pristup naprednim Stitch tokovima rada.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Istorija_Izrade_MOC]]

## Detaljan Opis / Tehnički Detalji
Zvanični repozitorijum sa skill-ovima [stitch-skills](https://github.com/google-labs-code/stitch-skills) je kloniran i njegovi plugini su instalirani na lokaciju `/home/gruya/.gemini/config/plugins/`.

Instalirani su sledeći plugini:
1. **`stitch-design`**:
   - Skilovi: `code-to-design`, `generate-design`, `manage-design-system`, `extract-design-md`, `extract-static-html`, `upload-to-stitch`.
   - Služi za integraciju kodnih baza sa Stitch dizajn interfejsom, preuzimanje i slanje dizajna.
2. **`stitch-build`**:
   - Skilovi: `react-components`, `react-native`, `remotion`, `shadcn-ui`.
   - Omogućava automatsko generisanje koda (komponenti, ekrana) na osnovu Stitch dizajna.
3. **`stitch-utilities`**:
   - Skilovi: `design-md`, `enhance-prompt`, `stitch-loop`, `taste-design`.
   - Pomoćni alati za poboljšanje promptova za dizajn i proveru kvaliteta (Design Quality Audit).

### Verifikacija instalacije:
Sva tri plugin direktorijuma su uspešno prekopirana i nalaze se na putanji:
- [stitch-design](file:///home/gruya/.gemini/config/plugins/stitch-design)
- [stitch-build](file:///home/gruya/.gemini/config/plugins/stitch-build)
- [stitch-utilities](file:///home/gruya/.gemini/config/plugins/stitch-utilities)

## Istorijat Izmena
*   **2026-06-22**: Kloniranje i instalacija Stitch-Skills - Antigravity.
