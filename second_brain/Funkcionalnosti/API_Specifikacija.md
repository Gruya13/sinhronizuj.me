# API Specifikacija (OpenAPI)

Ovaj dokument je automatski generisan iz OpenAPI šeme FastAPI aplikacije.

## Povezane Beleške
*   [[00_MOC_Index]]
*   [[Backend]]

---

## API Endpoint-i

### `POST` /api/v1/waitlist
**Naziv:** Add To Waitlist  
**Tagovi:** `Auth`  
**Opis:** Dodavanje korisnika na listu čekanja (Waitlist) za zatvorenu betu.  

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - WaitlistRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/auth/register
**Naziv:** Register User  
**Tagovi:** `Auth`  
**Opis:** Registracija novog korisničkog naloga.  

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - UserRegisterRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/auth/login
**Naziv:** Login User  
**Tagovi:** `Auth`  
**Opis:** Prijava korisnika i generisanje JWT tokena.  

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - UserLoginRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /api/v1/auth/me
**Naziv:** Get Me  
**Tagovi:** `Auth`  
**Opis:** Profil ulogovanog korisnika na osnovu JWT tokena.  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `POST` /api/v1/auth/logout
**Naziv:** Logout  
**Tagovi:** `Auth`  
**Opis:** Dodaje trenutni JWT token u blocklistu u Redisu do isteka njegovog važenja.  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `GET` /api/v1/storage/upload_url
**Naziv:** Get Upload Url  
**Tagovi:** `Projects`  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `filename` | `string` | `query` | Da |  |
| `project_id` | `string` | `query` | Da |  |
| `content_type` | `string` | `query` | Ne |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/process-video
**Naziv:** Process Video  
**Tagovi:** `Projects`  
**Opis:** Pokreće asinhronu analizu videa (Faza 1). Zahteva proveru vlasništva, kvota i limita.  

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - VideoRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/project
**Naziv:** Create Project  
**Tagovi:** `Projects`  
**Opis:** Kreira projekat u PostgreSQL bazi.  

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - CreateProjectRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /api/v1/projects
**Naziv:** List Projects  
**Tagovi:** `Projects`  
**Opis:** Izlistava projekte koji pripadaju isključivo ulogovanom korisniku iz baze podataka.  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `DELETE` /api/v1/project/{project_id}
**Naziv:** Delete Project  
**Tagovi:** `Projects`  
**Opis:** Briše projekat iz PostgreSQL-a i briše povezane fajlove sa S3 skladišta.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /api/v1/project/{project_id}
**Naziv:** Get Project Draft  
**Tagovi:** `Projects`  
**Opis:** Učitava nacrt projekta i segmente iz baze podataka, sa generisanjem presigned URL-ova.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/project/{project_id}/save
**Naziv:** Save Project Draft  
**Tagovi:** `Projects`  
**Opis:** Čuva najnovije izmene segmenata prevoda u PostgreSQL bazu.
Optimizovano: Rešen N+1 upit i batch-ovano slanje glosara.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - SaveProjectRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/project/{project_id}/segment/{segment_id}/shorten
**Naziv:** Shorten Segment Translation  
**Tagovi:** `Segments`  
**Opis:** AI Lektura za skraćivanje teksta uz proveru vlasništva.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |
| `segment_id` | `integer` | `path` | Da |  |

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - ShortenSegmentRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/project/{project_id}/segment/{segment_id}/tts
**Naziv:** Generate Segment Tts  
**Tagovi:** `Segments`  
**Opis:** Sinteza pojedinačnog segmenta govora u asinhronom režimu preko Celery-ja.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |
| `segment_id` | `integer` | `path` | Da |  |

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - SegmentTTSRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/project/{project_id}/generate-all-tts
**Naziv:** Generate All Tts  
**Tagovi:** `Segments`  
**Opis:** Sinteza glasa za ceo video u asinhronom režimu preko Celery-ja.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - GenerateAllTTSRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/project/{project_id}/render
**Naziv:** Render Project  
**Tagovi:** `Segments`  
**Opis:** Pokretanje finalnog renderovanja (Faza 2) uz proveru vlasništva.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - RenderRequest]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /api/v1/admin/stats
**Naziv:** Get Admin Stats  
**Tagovi:** `Admin`  
**Opis:** Vraća globalne statistike sistema za Dashboard administratora.  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `GET` /api/v1/admin/waitlist
**Naziv:** Get Admin Waitlist  
**Tagovi:** `Admin`  
**Opis:** Vraća listu svih prijava za zatvorenu betu.  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `POST` /api/v1/admin/waitlist/{waitlist_id}/approve
**Naziv:** Approve Waitlist Entry  
**Tagovi:** `Admin`  
**Opis:** Odobrava prijavu na listu čekanja.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `waitlist_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/admin/waitlist/{waitlist_id}/reject
**Naziv:** Reject Waitlist Entry  
**Tagovi:** `Admin`  
**Opis:** Odbija prijavu na listu čekanja.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `waitlist_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /api/v1/admin/users
**Naziv:** Get Admin Users  
**Tagovi:** `Admin`  
**Opis:** Vraća listu svih registrovanih korisnika sa statistikom o projektima i troškovima.  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `POST` /api/v1/admin/users/{user_id}/toggle-admin
**Naziv:** Toggle User Admin  
**Tagovi:** `Admin`  
**Opis:** Dodeljuje ili oduzima administratorske privilegije korisniku.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `user_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /api/v1/admin/projects
**Naziv:** Get Admin Projects  
**Tagovi:** `Admin`  
**Opis:** Vraća listu svih projekata u sistemu.  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `GET` /api/v1/admin/project/{project_id}
**Naziv:** Get Admin Project Detail  
**Tagovi:** `Admin`  
**Opis:** Vraća detaljan uvid u projekat (segmenti, S3 putanje, detaljni troškovi i logovi).  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `project_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /api/v1/status/{task_id}
**Naziv:** Get Task Status  
**Tagovi:** `System`  
**Opis:** Vraća status Celery taska uz proveru vlasništva nad projektom.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `task_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `POST` /api/v1/warmup
**Naziv:** Warmup Workers  
**Tagovi:** `System`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `GET` /api/v1/modal-status
**Naziv:** Get Modal Global Status  
**Tagovi:** `System`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `GET` /api/v1/hw-stats
**Naziv:** Hw Stats  
**Tagovi:** `System`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `GET` /api/v1/logs
**Naziv:** Get Worker Logs  
**Tagovi:** `System`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `POST` /api/v1/flush-redis
**Naziv:** Flush Redis  
**Tagovi:** `System`  
**Opis:** Čisti Redis keš (samo neaktivne projekte stare preko 7 dana).  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

### `GET` /api/v1/wiki/rules
**Naziv:** List Wiki Rules  
**Tagovi:** `Wiki Rules`  
**Opis:** Vraća sva Wiki pravila dostupna korisniku (njegova lokalna + globalna pravila).  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `array` |

---

### `POST` /api/v1/wiki/rules
**Naziv:** Create Wiki Rule  
**Tagovi:** `Wiki Rules`  
**Opis:** Kreira novo Wiki pravilo za ulogovanog korisnika.  

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - WikiRuleCreate]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | `[[#Schema - WikiRuleResponse]]` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `PUT` /api/v1/wiki/rule/{rule_id}
**Naziv:** Update Wiki Rule  
**Tagovi:** `Wiki Rules`  
**Opis:** Ažurira postojeće Wiki pravilo korisnika.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `rule_id` | `string` | `path` | Da |  |

#### Zahtev (Request Body)
Tip sadržaja: `application/json`  
Šema zahteva: `[[#Schema - WikiRuleUpdate]]`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | `[[#Schema - WikiRuleResponse]]` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `DELETE` /api/v1/wiki/rule/{rule_id}
**Naziv:** Delete Wiki Rule  
**Tagovi:** `Wiki Rules`  
**Opis:** Briše Wiki pravilo korisnika.  

#### Parametri
| Naziv | Tip | Lokacija | Obavezno | Opis |
|---|---|---|---|---|
| `rule_id` | `string` | `path` | Da |  |

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |
| `422` | Validation Error | `[[#Schema - HTTPValidationError]]` |

---

### `GET` /
**Naziv:** Read Root  
**Tagovi:** `Nema`  

#### Odgovori (Responses)
| Kod | Opis | Šema |
|---|---|---|
| `200` | Successful Response | Inline `object` |

---

## Šeme Podataka (Schemas)

### Schema - CreateProjectRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `name` | `string` | Da |  |

---

### Schema - GenerateAllTTSRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `voice_type` | `string` | Ne |  |

---

### Schema - HTTPValidationError
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `detail` | `array` | Ne |  |

---

### Schema - RenderRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `voice_type` | `string` | Ne |  |
| `background_volume` | `number` | Ne |  |
| `dubbed_volume` | `number` | Ne |  |

---

### Schema - SaveProjectRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `segments` | `array` | Da |  |

---

### Schema - SegmentItem
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `id` | `integer` | Da |  |
| `start` | `number` | Da |  |
| `end` | `number` | Da |  |
| `original` | `string` | Da |  |
| `translated` | `string` | Da |  |
| `tts_path` | `string` / `null` | Ne |  |
| `tts_duration` | `number` / `null` | Ne |  |
| `status` | `string` / `null` | Ne |  |
| `voice_type` | `string` / `null` | Ne |  |
| `volume` | `number` / `null` | Ne |  |
| `speed` | `number` / `null` | Ne |  |
| `pitch` | `number` / `null` | Ne |  |
| `bg_volume` | `number` / `null` | Ne |  |
| `active_speaker` | `boolean` / `null` | Ne |  |

---

### Schema - SegmentTTSRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `text` | `string` | Da |  |
| `voice_type` | `string` | Ne |  |
| `volume` | `number` | Ne |  |
| `speed` | `number` | Ne |  |
| `pitch` | `number` | Ne |  |
| `bg_volume` | `number` | Ne |  |

---

### Schema - ShortenSegmentRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `text` | `string` | Da |  |

---

### Schema - UserLoginRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `email` | `string` | Da |  |
| `password` | `string` | Da |  |

---

### Schema - UserRegisterRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `email` | `string` | Da |  |
| `password` | `string` | Da |  |

---

### Schema - ValidationError
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `loc` | `array` | Da |  |
| `msg` | `string` | Da |  |
| `type` | `string` | Da |  |
| `input` | `` | Ne |  |
| `ctx` | `object` | Ne |  |

---

### Schema - VideoRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `url` | `string` | Da |  |
| `debug` | `boolean` | Ne |  |
| `project_id` | `string` / `null` | Ne |  |

---

### Schema - WaitlistRequest
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `email` | `string` | Da |  |

---

### Schema - WikiRuleCreate
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `title` | `string` | Da |  |
| `content` | `string` | Da |  |
| `category` | `string` / `null` | Ne |  |
| `is_global` | `boolean` / `null` | Ne |  |

---

### Schema - WikiRuleResponse
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `id` | `string` | Da |  |
| `user_id` | `string` | Da |  |
| `title` | `string` | Da |  |
| `content` | `string` | Da |  |
| `category` | `string` | Da |  |
| `is_global` | `boolean` | Da |  |
| `created_at` | `string` | Da |  |

---

### Schema - WikiRuleUpdate
| Polje | Tip | Obavezno | Opis |
|---|---|---|---|
| `title` | `string` / `null` | Ne |  |
| `content` | `string` / `null` | Ne |  |
| `category` | `string` / `null` | Ne |  |
| `is_global` | `boolean` / `null` | Ne |  |

---
