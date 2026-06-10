# PID Odjezdy — odjezdová tabule pro Home Assistant

Vlastní integrace Home Assistantu zobrazující **odjezdy PID** (Pražská integrovaná doprava) pro zvolenou zastávku. Data poskytuje [Golemio API](https://api.golemio.cz/pid/docs/openapi/) (datová platforma hl. m. Prahy).

## Funkce

- **Odjezdová tabule jako jedna entita** — stav senzoru je čas nejbližšího odjezdu, atribut `departures` obsahuje celou tabuli (konfigurovatelný počet spojů, 1–20).
- **Výluky a mimořádnosti** — samostatný senzor s infotexty pro zastávku.
- **Dostupnost API** — diagnostický binary sensor; když Golemio neodpovídá, tabule to pozná.
- **Více zastávek** — každá zastávka je samostatná instance integrace (vlastní zařízení).
- **Filtry** — podle linek (např. jen `332, 339`) a nástupišť/směru (např. jen `A`).
- Zpoždění, plánovaný i predikovaný čas, klimatizace, bezbariérovost, zrušené spoje, cílová/poslední zastávka, číslo vlaku (S-linky).

## Instalace

### HACS (doporučeno)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Přidej `https://github.com/hruskin/ha-pid-odjezdy` jako *Integration*
3. Nainstaluj **PID Odjezdy** a restartuj Home Assistant

### Ručně

Zkopíruj `custom_components/pid_odjezdy/` do `config/custom_components/` a restartuj HA.

## Nastavení

1. Zařízení a služby → **Přidat integraci** → *PID Odjezdy*
2. Vlož **Golemio API token** — zdarma na [api.golemio.cz/api-keys](https://api.golemio.cz/api-keys)
3. Zadej **přesný název zastávky PID** (např. `Křížkový Újezdec`)

V **Možnostech** integrace pak lze měnit: počet spojů (výchozí 6), interval aktualizace (výchozí 60 s), časové okno dopředu, zobrazení zrušených spojů a filtry linek/nástupišť.

## Entity

| Entita | Stav | Atributy |
|---|---|---|
| `sensor.<zastavka>_odjezdy` | čas nejbližšího odjezdu (`timestamp`) | `departures` (pole spojů), `stop_name`, `platforms`, `next_route`, `next_headsign`, `next_display`, `updated_at` |
| `sensor.<zastavka>_vyluky` | počet aktivních výluk | `infotexts` (text, platnost) |
| `binary_sensor.<zastavka>_api` | dostupnost Golemio API | `last_success` |

Každý spoj v poli `departures`:

```yaml
route: "332"             # linka
type: "bus"              # bus / tram / metro / train / trolleybus…
headsign: "Praha, Budějovická"
scheduled: "2026-06-10T15:04:00+02:00"   # jízdní řád
predicted: "2026-06-10T15:06:00+02:00"   # predikce
minutes: 7               # minut do odjezdu
delay_min: 2             # zpoždění v minutách
delay_available: true
platform: "A"            # nástupiště (směr)
air_conditioned: true
wheelchair_accessible: true
canceled: false
at_stop: false           # vůz stojí na zastávce
last_stop: "Praha, Budějovická"
train_number: null       # u vlaků např. "S9"
display: "15:06(+2)"     # hotový text pro tabuli
```

## Příklad karty (Markdown)

```yaml
type: markdown
title: Odjezdy
content: |
  {% for d in state_attr('sensor.krizkovy_ujezdec_odjezdy', 'departures') %}
  **{{ d.route }}** → {{ d.headsign }} — **{{ d.display }}**
  ({{ d.minutes }} min){{ ' ❄️' if d.air_conditioned }}{{ ' ♿' if d.wheelchair_accessible }}{{ ' ⛔ ZRUŠEN' if d.canceled }}
  {% endfor %}
```

## Poznámky

- Data: © [Golemio](https://golemio.cz) / ROPID. Integrace není oficiálním produktem PID ani Golemia.
- Token se ukládá v konfiguraci HA, do repozitáře nikdy nepatří.
- Integrace vznikla jako náhrada Node-RED flow s šesti `ha-sensor` uzly.

## Licence

Apache 2.0
