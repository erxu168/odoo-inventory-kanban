# Restaurant Locations (`restaurant_location`)

Odoo 19 · depends on `base`, `mail`

One record per restaurant site, holding everything that is bound to the
**building** rather than to the business day: the lease and landlord, supply
and service contracts, meters and their readings, waste and recycling
pickups, insurance policies, permits and inspections, and the people to call.

It is a **separate app** with its own models (`restaurant.location.*`). It
shares nothing with the Portal's Rentals module or with `krawings_contract`
beyond the ideas that worked there: a contract carries its notice period so
the *cancel-by* date is computed, readings live on the meter and not on the
supplier, and every recurring cost is annualised so sites can be compared.

## What goes where

| Model | One row is… | Highlights |
|---|---|---|
| `restaurant.location` | a site | Address, seats, floor area, trade registration, tax and broadcasting-fee numbers. Landlord, property manager and lease summary are pulled from the active lease contract. Managers and staff users per site drive the record rules. |
| `restaurant.location.contract` | any recurring agreement | Types: lease, electricity, gas, water, district heating, telecom, waste, insurance, service, other. Contract vs. customer number, term, **notice period → cancel-by date**, auto-renewal, price guarantee, portal login, documents. Type-specific groups: rent breakdown and deposit; base fee / unit price / instalment; policy number, sum insured, deductible, main due date; service interval. |
| `restaurant.location.meter` | a physical meter | Type, number, MaLo-ID, metering point, grid operator, calibration date, conversion factor (gas m³ → kWh). Points at the contract that currently supplies it. Reading interval with an overdue flag. |
| `restaurant.location.meter.reading` | one reading | Consumption, days elapsed, daily average and billed units against the previous reading; indicative cost from the contract in force on that date. Readings may not go backwards. Optional photo. |
| `restaurant.location.waste.type` | a fraction | Seeded: Restmüll, Gewerbeabfall, Gelbe Tonne, Glas, Papier, Bio, Speisereste (Kat. 3), Altfett, Fettabscheider, Sperrmüll. Configurable. |
| `restaurant.location.waste.stream` | one container service | Hauler, container size and count, where the bins stand, and the **pickup rhythm**: weekly (one or two weekdays), every 2 weeks on odd or even ISO calendar weeks, every 4 weeks, or the *n*-th weekday of the month. |
| `restaurant.location.waste.pickup` | one collection day | Generated eight weeks ahead from the rhythm; shown on a calendar; ticked off as collected / missed with container count, weight and certificate number. |
| `restaurant.location.compliance.type` | an obligation | Seeded with the usual German restaurant checks and their intervals (see below). |
| `restaurant.location.compliance` | that obligation at one site | Last done → due date, reminder window, authority, reference, certificates. *Done Today* rolls the next date. |
| `restaurant.location.contact` | who to call | Role (caretaker, electrician, HVAC, pest control…), phone, availability. |

## Deadlines and reminders

Four daily scheduled actions, all idempotent:

* **Contract deadlines & auto-renewals** — an activity for the responsible
  user at 90, 60 and 30 days before the cancel-by date. Editing the end date
  or notice period resets the reminders. A contract whose term has passed
  without a cancellation, and which auto-renews, has its end date pushed
  forward by the renewal period and a note posted in the chatter, so the
  next cancel-by date is already right.
* **Meter reading reminders** — one open activity per meter whose last
  reading is older than its interval.
* **Plan waste pickups** — keeps every active stream's calendar filled for
  the configured horizon and marks pickups nobody confirmed within three days
  as *missed*.
* **Permit & inspection reminders** — one activity per item when it enters
  its reminder window.

Status fields (`expiring`, `due`, `overdue`) are computed from today's date
on read, so lists are always current even before the cron has run.

## Waste pickup rules

Berlin haulers quote a weekday plus "gerade/ungerade KW". The stream stores
exactly that and the module expands it into dated pickups:

| Rhythm | Rule |
|---|---|
| Every week | the weekday (optionally two) |
| Every 2 weeks, odd / even | weekday, ISO week number odd / even |
| Every 4 weeks | weekday, anchored on the first planned pickup |
| Monthly | first … fourth / last weekday of the month |
| On call | nothing is planned |

Changing the rule deletes untouched *planned* future pickups and re-plans
them; confirmed and missed ones are kept, so the disposal record survives a
change of hauler.

## Seeded standard checks

*Add Standard Checks* on a location creates the items below that it does not
already have. Intervals are the common ones and can be changed per site.

| Check | Every | Basis |
|---|---|---|
| Trade registration (Gewerbeanmeldung) | once | § 14 GewO |
| Restaurant licence (Gaststättenerlaubnis) | once | GastG |
| Hygiene briefing (IfSG § 43) | 24 months | § 43 IfSG |
| Grease trap emptying | 1 month | DIN 4040-100 |
| Grease trap general inspection | 60 months | DIN 4040-100 |
| Kitchen exhaust cleaning | 12 months | VDI 2052 / VdS 2056 |
| Fire extinguishers | 24 months | DIN 14406-4 |
| Electrical safety (DGUV V3) | 12 months | DGUV V3 |
| Pest control visit | 3 months | HACCP |
| First-aider refresher | 24 months | DGUV V1 |

Non-standard types (food-safety inspection, dispensing system, GEMA, outdoor
seating permit) are available but added by hand.

## Security

| Group | Can |
|---|---|
| Staff | see the sites they are listed on; add meter readings; confirm pickups |
| Location Manager | everything on their sites, including portal logins and PINs |
| Owner / Admin | all sites, deletion, configuration |

Portal login, password and phone PIN are only readable by managers
(`groups` on the fields). Multi-company rules are global on every model.

## Not in scope (deliberately)

* Turning meter readings into an invoice check (Abschlag drift,
  Betriebskostenabrechnung). The estimated cost is indicative only.
* Fetching readings from smart meters or supplier portals.
* Public-holiday shifting of pickup days: haulers handle it differently;
  use the schedule note and adjust the affected pickup.
* Linking to `pos.config` or `hr.work.location` — kept dependency-free;
  add a bridge module if needed.

## Tests

```bash
odoo-bin -d <db> -i restaurant_location --test-enable --test-tags /restaurant_location --stop-after-init
```
