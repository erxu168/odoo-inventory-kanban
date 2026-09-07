# Automated Shift Planning — Design Proposal

**Status:** proposal, not implemented
**Scope:** turn the Planning module from "Rogers builds the roster by hand" into
"Rogers sets the parameters, the system builds the roster and Rogers approves it"

---

## 1. The problem in one sentence

Today one manager holds the whole roster in their head: who is free, who is
capped on hours, who is weak on a Friday, who must not close two nights in a
row. That knowledge is not written down anywhere, so it cannot be automated,
audited, or handed to a second location.

The fix is not "an algorithm". The fix is **writing that knowledge down as
data**, and only then letting a solver read it. Every hour spent on the data
model pays back; an algorithm on top of undeclared rules just produces a
roster nobody trusts.

Two data structures carry almost the whole design:

- **availability** — what each person offers (§2)
- **attributes and requirements** — what each person *is*, and what each shift
  *needs* (§5)

Everything else is bookkeeping around those two.

---

## 2. The central modelling decision: shifts, days, or time periods?

This is the question that decides whether the module works for one restaurant
or for any restaurant. The answer is: **all three, because they are the same
thing stored one way and displayed three ways.**

### Store availability as intervals with a preference score

```
availability line = (employee, date, time_from, time_to, preference)
preference ∈ {unavailable, available, preferred}
```

That is the only storage format. It cannot be outgrown.

### Display it as whatever the restaurant's shift patterns imply

Each restaurant defines its own **shift templates** (Odoo already has these:
`planning.slot.template` — a start time, a duration, a role). Today you have
two. Another restaurant defines five. A café defines one. A hotel defines
"Early / Late / Night".

The staff-facing grid is generated *from* those templates:

| Granularity mode | What staff see | What gets stored |
|---|---|---|
| `shift` (your case) | Date × [Early, Late] with 3-state buttons | Two intervals per day, from the template times |
| `day` | Date × [Whole day] | 00:00–23:59 for that date |
| `range` | "From 10:00 to 16:00" free entry | Exactly what they typed |

So the *principle* — "staff indicate when they can work" — is constant, and the
granularity is a per-restaurant setting, not a code change. A slot is coverable
by a person when the person's available intervals cover the slot's interval.

### Why three states and not a checkbox

`unavailable / available / preferred` costs the staff member nothing extra
(three buttons instead of one) and gives the scheduler the single most valuable
piece of information there is: the difference between *can* and *wants to*.
With a checkbox, the system has to treat a reluctant yes and an eager yes
identically, and people learn to just untick things. Keep it at three — four or
five states (e.g. "only if needed") sound better in a meeting and get filled in
randomly in practice.

---

## 3. The workflow

```
  ┌──────────────┐   cron    ┌───────────┐  cron   ┌──────────┐
  │ Period draft │──────────▶│  OPEN     │────────▶│  CLOSED  │
  │ Rogers sets  │  opens    │ staff     │ deadline│ no more  │
  │ dates+rules  │           │ submit    │         │ changes  │
  └──────────────┘           └───────────┘         └────┬─────┘
                                   ▲                    │ auto
                              reminders                 ▼
                            (T-7, T-2, T-1)      ┌─────────────┐
                                                 │  GENERATED  │
                                                 │ draft slots │
                                                 │ + score     │
                                                 │ + reasons   │
                                                 └──────┬──────┘
                                                        │ Rogers reviews,
                                                        │ drags, re-runs
                                                        ▼
                                                 ┌─────────────┐
                                                 │  PUBLISHED  │
                                                 │ Odoo Planning│
                                                 │ notifies all │
                                                 └─────────────┘
```

**Rogers' job afterwards** is: maintain the coverage matrix, maintain staff
attributes and shift requirements, set the weights, and approve. That is a
~30 minute/month job instead of a full day, and it is a job a second manager
can take over because it is all on screen.

### The non-responder rule (must be decided up front)

Someone will not submit. Configurable per period:

- `unavailable` — safest, but a silent person disappears from the roster
- `available` — fills the roster but schedules people who may not show
- `carry_forward` — **recommended default**: reuse their last submitted
  pattern, flag the slots as "assumed" so Rogers can eyeball them

Plus a "same as last period" button in the staff UI, which is what most people
will actually use.

### The anti-gaming rule (the one everybody forgets)

If availability is free-form, everybody blocks Friday and Saturday and the
roster cannot be filled. You need a **minimum availability obligation** before
a submission is accepted:

- must offer at least `availability_factor` × target hours (e.g. 1.5× — a
  40h/month Minijobber must mark ~60h of availability)
- must offer at least `min_weekend_shifts` weekend shifts per period
- must offer at least `min_days` distinct days

The submit button refuses until the quota is met, and tells them what is
missing. Set the factor per contract type: full-timers 1.2×, students 2.0×.
Without this rule the whole system collapses in month two — this is the single
most important parameter in the design.

---

## 4. Constraints: the hard/soft split

Everything the manager knows becomes a constraint, and every constraint is
either **hard** (a roster violating it is invalid) or **soft** (weighted, the
optimiser trades it off). Getting a rule into the right bucket is most of the
design work.

### Hard constraints — never violated

| # | Constraint | Source |
|---|---|---|
| H1 | Staff marked unavailable are not scheduled | availability |
| H2 | Approved time off blocks the slot | `hr.leave` (already in Odoo) |
| H3 | One person, one slot at a time | structural |
| H4 | Role qualification — only staff holding the role | `planning.role` |
| H5 | **All hard shift requirements met** — per-person and per-team | attributes (§5) |
| H6 | Manager block: person X never on weekday Y / shift Z | per-person rule |
| H7 | Contract hour cap for the period | `hr.employee` |
| H8 | **Minijob earnings cap** — €603/month, 43.38 h at €13.90 (2026) | law + payroll |
| H9 | Max daily hours: 8h, 10h with 24-week averaging | ArbZG §3 |
| H10 | Min rest between shifts: 11h; gastronomy may cut to 10h **only if** compensated by a 12h rest within 4 weeks | ArbZG §5 |
| H11 | Max 6 working days per week, Sunday rest, ≥15 free Sundays/year | ArbZG §9/§11 |
| H12 | Minors: no work after 22:00, 8h/day, 5-day week | JArbSchG |
| H13 | Roster published ≥4 days before the first shift | TzBfG §12(3) |

H8 deserves emphasis: it must be enforced in **euros**, not only hours,
because hourly rates differ. Pushing a Minijobber to €610 costs the business
far more than the extra shift is worth, and it is invisible until payroll.
The scheduler should hard-stop at the cap and warn Rogers at 80%.

H13 is the legal floor on how late the window may close. It is not the
recommended value — plan for 2–3 weeks.

### Soft constraints — weighted, Rogers tunes them

Each has a weight 0–10; weight 0 disables it. The optimiser maximises the
weighted sum.

| # | Objective | Notes |
|---|---|---|
| S1 | Honour `preferred` over `available` | the core satisfaction driver |
| S2 | Land everyone near their target hours | penalise both under and over |
| S3 | Fair share of *undesirable* shifts | see the credit ledger, §7 |
| S4 | **Soft shift requirements met** | "prefer a second keyholder" (§5) |
| S5 | **Best fit, not best person** | don't overshoot the requirement (§5) |
| S6 | Schedule consistency week to week | hugely underrated; staff plan their lives around it, and familiar teams make fewer mistakes |
| S7 | No "clopening" (close then open next morning) | legal at 10h rest, still corrosive |
| S8 | Minimise split shifts | cap per person per week |
| S9 | Labour cost within the day's budget | see §6 |
| S10 | Pairing rules: A works well with B / never A with B | quiet but real |
| S11 | Guarantee ≥2 consecutive days off | retention |
| S12 | Guarantee N free weekends per period | retention |
| S13 | Prefer longer shifts for commuters | a 4h shift for a 50-min commute is a resignation letter |
| S14 | Minimise change vs the previous published version | so a re-run doesn't reshuffle everything |

S14 matters more than it looks. Once Rogers has hand-adjusted a draft, a re-run
must not throw his edits away. Pin manually-edited slots and re-optimise only
around them.

---

## 5. Attributes and requirements — one mechanism for all matching

**Staff carry attributes. Shift templates declare requirements over those
attributes. Matching is one function.** Adding a new rule later is a data
row, not a code change — which is the whole point, because you will think of
new rules for years and none of them should need a developer.

### 5.1 Attribute definitions

`restaurant.staff.attribute` — Rogers defines these once.

| Value type | Examples | Requirement form |
|---|---|---|
| `flag` | keyholder, till-trained, can drive, closing-certified | must be true |
| `level` (0–5) | grill, bar, service speed, guest handling, German | must be ≥ N |
| `certification` | IfSG §43 hygiene, first aid, alcohol service | must be **valid on the shift's date** |
| `computed` | reliability, tenure days, hours booked this period | must be ≥ / ≤ N |

Four types is enough. A certification is a flag with validity dates; a computed
attribute is a level or number that a nightly cron writes instead of a human.
That last one is what unifies things: **the reliability score from §6 is just
another attribute**, so the strong-day rule needs no special-case code.

Fields: `code`, `name`, `category`, `value_type`, `scale_min`, `scale_max`,
`compute_method`, `expires`, `review_interval_months`.

### 5.2 Staff values — effective dated, not overwritten

`restaurant.staff.attribute.value`:
`employee_id, attribute_id, value_bool, value_number, valid_from, valid_until,
source (manual|computed), note, evidence attachment`

Effective dating is not optional. Overwrite a value in place and you can no
longer explain last month's roster, and you cannot prove to an inspector that a
hygiene certificate was valid on the day someone worked. Promotions, expiries
and score changes all become new rows.

### 5.3 Requirements — the two scopes that matter

This is the distinction that makes or breaks the design:

- **`each`** — *every* person assigned to the slot must satisfy it.
  "Everyone on shift holds a valid hygiene certificate."
- **`team`** — the *crew as a whole* must satisfy it.
  "At least one keyholder." "At most one trainee." "Average speed ≥ 3.5."

Per-person rules cannot express "one keyholder". Team rules cannot express
"nobody without hygiene training". You need both — and they are the same table
with a `scope` field, not two subsystems.

`restaurant.shift.requirement`:

```
attribute_id      which attribute
scope             each | team
operator          >= | <= | == | is_true | is_valid
value             threshold (number) where applicable
aggregate         team only: count | avg | sum | min | max
min_count         team + count: at least N people satisfy it
max_count         team + count: at most N people satisfy it
enforcement       hard | soft
weight            0–10, used when soft
weekday_filter    optional: only Fri/Sat, or a date range
message           what Rogers sees when it fails
```

Worked examples — every one of these is a data row, no code:

| Rule in plain English | scope | aggregate | operator | value | count |
|---|---|---|---|---|---|
| Everyone must be hygiene-certified | each | — | is_valid | — | — |
| Nobody below service speed 2 | each | — | `>=` | 2 | — |
| At least one keyholder on shift | team | count | is_true | — | min 1 |
| At least two who can run the grill at 4+ | team | count | `>=` | 4 | min 2 |
| Team average speed at least 3.5 | team | avg | `>=` | 3.5 | — |
| At most one person with under 30 days' tenure | team | count | `<=` | 30 | max 1 |
| **Fri/Sat: everyone reliability ≥ 70** | each | — | `>=` | 70 | — *(weekday filter)* |

That last row is exactly your "certain people shouldn't work the strong days"
rule — expressed as data, applied automatically, and self-correcting as
someone's score improves. Nobody has to re-decide it, and nobody has to defend
it in person.

### 5.4 Where requirements attach

- on a **shift template** → applies to that shift wherever it is used
- on a **coverage line** (shift × role × headcount) → applies only to the
  people filling that role on that shift
- with an optional **weekday or date filter** → Friday's bar is stricter than
  Tuesday's, without duplicating the template

Both sets apply together; where they overlap, the stricter one wins. That keeps
"Saturday Late" from becoming a separate hand-maintained template that drifts
out of sync with the weekday one.

### 5.5 One matching function, three surfaces

```
_evaluate(slot, crew) → (ok: bool, failures: [(requirement, reason)])
```

The same call powers:

1. **the scheduler** — hard filter on candidates, soft score on the rest
2. **manual override** — Rogers drags someone in and immediately sees
   "Anna: hygiene certificate expired 12 Aug" rather than finding out later
3. **the gap report, run *before* the window closes** —
   "Saturday Late needs 2 × grill ≥ 4; only 1 qualifying person has marked
   themselves available"

Surface 3 may be worth as much as the auto-scheduling itself. It converts a
Friday-evening crisis into a Tuesday phone call, and it works even in phase 1
while Rogers is still assigning by hand.

### 5.6 Best fit, not best person

A non-obvious scoring rule, and the one most systems get wrong: when several
candidates clear the bar, prefer the one who *just* clears it — not the
strongest.

Assigning your best griller to every shift that mentions the grill starves the
shifts that genuinely need them, and burns that person out. So score
**overshoot negatively**, with a weight that lets Rogers dial between "safest
hands on every shift" and "efficient use of talent".

The corollary is a **development objective**: occasionally place someone one
level *below* the requirement on a shift where a mentor at level+2 is present,
so people actually grow into the higher levels. Cap it (N development
placements per period), never on a high-demand day, and always with the mentor
requirement enforced as hard. Otherwise your level-4 pool never grows and the
schedule gets more brittle every month.

### 5.7 Keeping the attribute set from rotting

The failure mode of every attribute system is forty attributes nobody
maintains. Four defences, all cheap:

- **Usage counter** — show "referenced by N requirements" on each attribute. An
  attribute no requirement references is dead weight; archive it.
- **Review intervals** — per attribute, flag values not reviewed in N months.
  A skill level from two years ago is fiction.
- **Expiry handling** — certifications auto-block on expiry and warn the
  employee and Rogers 30 days ahead. This has to be automatic; nobody tracks
  certificate dates by hand for long.
- **Over-constraint report** — after each run, name the requirement responsible
  for the most unfilled slots. Requirements ratchet upward on their own, and
  without this feedback the roster quietly becomes unfillable.

### 5.8 What this one mechanism replaces

Skill levels per role, minimum skill points per shift, the keyholder rule, the
first-aider rule, language coverage, trainee limits, reliability thresholds on
strong days, certification checks, and the manual "X shouldn't work Fridays"
block — all of them collapse into attribute values plus requirement rows. That
is the difference between a module you extend by writing Python and one Rogers
extends himself on a Tuesday afternoon.

---

## 6. Parameters you did not ask about

You asked what else is out there. These are the ones that pay for themselves,
grouped by where they come from.

### Demand side — how many people do we actually need?

Right now the demand is implicit in Rogers' head. Make it a **coverage matrix**:
weekday × shift × role → headcount, with per-date overrides for holidays,
events, and closures, and the requirement rows from §5 hanging off each line.
That alone removes half the manual work.

Then, later, the coverage can be *derived* rather than typed:

- **forecast covers / revenue per daypart** from POS history (same weekday,
  trailing weeks, plus year-over-year)
- **labour cost as % of forecast revenue** — the industry's actual control
  number; give each day a € budget and let the optimiser respect it
- **sales per labour hour** as the efficiency target
- local events, school holidays, weather (a beer garden's Saturday is a weather
  function), delivery-platform peak windows, reservation book

Start with the hand-typed matrix. Derive it in phase 4, when there is history.

### Data you already collect and are not using yet

This repository already tracks, per shift, **task completion score**
(`restaurant.task.list.completion_score`) and **attendance**
(`hr.attendance`, plus `avg_task_completion` on `hr.employee`). That is exactly
the raw material for a **computed reliability attribute** (§5.1):

```
reliability = w1·avg_task_completion
            + w2·(1 − no_show_rate)
            + w3·(1 − late_check_in_rate)
            + w4·(1 − shift_overrun_rate)
```

Computed nightly over a rolling 8–12 weeks — not lifetime, so a bad month is
recoverable — and written as an attribute value like any other. Then the
Friday/Saturday rule from §5.3 picks it up with no further work, and someone
whose scores improve earns their way back onto the strong days automatically.
Keep a manual override on the employee record for the cases the data misses.

### Financial

- overtime avoidance (schedule to target, keep a buffer)
- Minijob cap alerting at 80% / 100% (H8)
- avoid accidentally pushing someone from Minijob into Midijob territory
- night premium hours (tax-free supplements after 20:00) as a cost input
- holiday and Sunday premiums

### Human factors

- blocked personal dates (a birthday, an exam) separate from ordinary
  availability, with a small annual quota so they stay meaningful
- students' exam periods
- last public transport → cannot take a closing shift (a `flag` attribute plus
  a requirement on closing templates)
- seniority as a tiebreak only, never as a hard rule
- a "wants more hours" flag — the cheapest way to fill an open shift is to ask
  the person who has been asking for more

---

## 7. The fairness credit ledger

Fairness is the thing rosters get accused of and the thing that is hardest to
argue about without numbers. A simple, explainable mechanism:

- every shift carries an **undesirability weight** set by Rogers (Sat close = 3,
  Tue lunch = 0)
- working it adds that weight to the employee's rolling credit
- when two people are equally eligible, the one with **lower credit** gets the
  unpopular slot
- credits decay over a rolling window (8–12 weeks) so they never freeze

It self-balances, it survives people joining and leaving mid-period, and — the
real benefit — Rogers can show the ledger to anyone who complains. Fairness
arguments end when there is a number on the screen.

---

## 8. Explainability is a feature, not a nicety

An auto-generated roster that cannot explain itself will be overridden until it
is abandoned. Every run must record, per decision:

- for each assignment: which requirements this person met and how well
- for each **unfilled** slot: why nobody could take it — "3 candidates: 2 hit
  the monthly cap, 1 fails the 11h rest rule after Thursday's close" — and, for
  requirement failures, *which* requirement and by how much
- for each person: hours vs target, cap headroom, fairness credit, preference
  match rate

That last one is also what you show the staff member: *this* is why you got
these shifts. It is the difference between "the computer decided" and "here is
the arithmetic".

Unfilled slots should not block publication. Publish them as Odoo **open
shifts** — staff can claim them, which is a native Planning feature and the
natural pressure valve for a roster that is 95% solved. Claiming an open shift
still runs `_evaluate`, so an unqualified person cannot self-assign.

---

## 9. Proposed data model

New models, following this repo's existing conventions
(`restaurant.*` prefix, `mail.thread` on the records that need a history):

| Model | Purpose |
|---|---|
| `restaurant.staff.attribute` | attribute definitions — flag / level / certification / computed (§5.1) |
| `restaurant.staff.attribute.value` | effective-dated value per employee (§5.2) |
| `restaurant.shift.requirement` | a requirement over an attribute, `each` or `team` scope, hard or soft (§5.3) |
| `restaurant.planning.period` | the window: date range, open/close datetimes, state, non-responder policy, generation weights |
| `restaurant.availability.request` | one per employee per period; state, submitted-on, quota check, portal token |
| `restaurant.availability.line` | `(date, time_from, time_to, preference)` — the storage format from §2 |
| `restaurant.coverage.rule` | weekday or date × shift template × role → headcount, plus its own requirement lines |
| `restaurant.schedule.rule` | per-employee or global constraint that isn't attribute-shaped (blocked weekday, pairing, max consecutive days) |
| `restaurant.schedule.run` | a generation attempt: score, log, violations, link to the created draft slots |
| `restaurant.fairness.ledger` | rolling credits per employee (§7) |

Extended:

| Model | Added |
|---|---|
| `hr.employee` | attribute values (o2m), target/min/max hours per period, earnings cap (€) and hourly cost, max consecutive days, min rest override, minor flag, "wants more hours" |
| `planning.slot` | link to the generating run, undesirability weight, assignment reason, requirement-check result, `is_pinned` (survives re-runs) |
| `planning.slot.template` | requirement lines (§5.4) |

Reused from Odoo, **not** rebuilt:

- `planning.slot` — the roster itself, with its Gantt view, publish & send,
  open shifts, and recurrence
- `planning.slot.template` — the shift patterns (§2), now carrying requirements
- `planning.role` — roles and role-based eligibility
- `hr.leave` — approved time off feeds H2 for free
- `resource.calendar` — contractual working schedules

Odoo Planning already has an **Auto Plan** button that fills open shifts by
role, availability and hour limits. It is a reasonable baseline and worth a
look before writing anything — but it has no notion of staff attributes, shift
requirements, earnings caps, fairness credits, or an availability window, which
is precisely the gap this proposal fills.

*(Field names on the Odoo side should be verified against the installed
version before implementation — Planning's internals move between releases.)*

---

## 10. The engine

For a restaurant — roughly 15–30 staff, 60–120 slots a month — a **greedy
construction plus local-search repair** in plain Python is the right tool:

1. **Filter**: for every slot, compute the candidate set passing all hard
   constraints, including per-person (`each`) requirements. Slots with zero
   candidates are reported immediately.
2. **Order**: schedule the most constrained slots first — fewest candidates,
   hardest team requirements. This is what makes greedy work; a slot needing
   two grill-4s must be filled before the general service shifts eat the pool.
3. **Score**: pick the candidate with the best weighted soft score, including
   the overshoot penalty from §5.6.
4. **Satisfy team requirements**: after each slot is filled, check `team`-scope
   requirements; if unmet, swap in a qualifying candidate rather than
   restarting. Team requirements are checked on the crew, so they can only be
   evaluated once a slot has provisional occupants.
5. **Repair**: local search — swap pairs of assignments while the total score
   improves, with a fixed iteration budget.
6. **Report**: score, per-assignment reasons, unfilled slots with causes, and
   the over-constraint summary from §5.7.

Deterministic (fixed random seed) so the same inputs give the same roster —
"I re-ran it and got something different" destroys trust fast.

Keep every constraint check as a small, independently testable function and
every weight as data. Then, if the restaurant grows past what heuristics handle
well, an OR-Tools CP-SAT backend can be swapped in behind the same interface
without touching the data model — the attribute/requirement tables translate
into CP-SAT constraints almost mechanically. Do not start there: CP-SAT is
harder to explain, harder to debug, and adds a dependency for a problem this
size.

---

## 11. Rollout

Each phase is independently useful — if you stop after any of them, you are
still better off than today.

| Phase | Delivers | Value on its own |
|---|---|---|
| **1** | Attributes + requirements + the `_evaluate` function; periods, availability window, staff grid, reminders, quota rule. Rogers still assigns manually, but gets live warnings and the gap report. | The data stops living in WhatsApp and in one person's head. Rogers finds out on Tuesday that Saturday has no qualified griller. |
| **2** | Coverage matrix + generator with **hard constraints only** → draft roster. | Legally-invalid, cap-breaking and under-qualified rosters become impossible. Most of the manual time disappears. |
| **3** | Soft objectives, weights, fairness ledger, best-fit scoring, explanations. | The roster stops merely being valid and starts being *good*, and defensible. |
| **4** | Computed reliability attribute from attendance + task data, demand forecast from POS, labour cost budget, development placements. | The system starts managing, not just scheduling. |

Phase 1 is worth building even if you never build phase 2 — and note that the
attribute work lands there, not later, because the gap report and the manual
warnings need it.

---

## 12. Open questions for Rogers

1. **Period length** — calendar month (matches the Minijob cap cleanly) or
   4-week cycle (matches rest-period compensation cleanly)? Monthly is
   recommended; the cap is the tighter constraint.
2. **Window timing** — e.g. opens on the 1st, closes on the 20th, published on
   the 25th for the following month. Legal floor is 4 days' notice; 2–3 weeks
   is what staff actually need.
3. **Where do staff submit** — Odoo backend (they already have accounts for the
   task module) or a tokenised portal link (works for staff without a login)?
4. **The starting attribute list.** Ten or so is the right size to launch with.
   A plausible first set: keyholder (flag), till-trained (flag), grill (level),
   bar (level), service speed (level), guest handling (level), German (level),
   hygiene certificate (cert), first aid (cert), reliability (computed),
   tenure days (computed).
5. **Level scale** — 0–3 or 0–5? Five is more expressive; three gets filled in
   more honestly. Recommend 0–3 (`none / learning / solo / can train others`)
   because the labels mean something concrete.
6. **Which requirements are hard vs soft?** "One keyholder per shift" is
   normally hard; "at least one senior" is normally soft. Hard is easier to
   explain; soft means a bad week still produces a roster.
7. **Who maintains attribute values, and how often?** They rot fast. A quarterly
   review, or an update prompt when a probation period ends, is the usual answer.
8. **What is the current no-show / late rate?** It determines whether the
   computed reliability attribute is worth building or a solution in search of
   a problem.

---

## Sources

- [Planning — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/applications/services/planning.html)
- [Minijob-Verdienstgrenze steigt 2026 auf 603 Euro — Deutsche Rentenversicherung](https://www.deutsche-rentenversicherung.de/BadenWuerttemberg/DE/Presse/Pressemitteilungen/2025/251222_Minijob)
- [Minijobs 2026: neue Grenzen & Tipps für Arbeitgeber — AOK](https://www.aok.de/fk/jahreswechsel/aenderungen-bei-minijobs/)
- [Arbeitszeitgesetz Gastronomie – Pausen, Ruhezeiten & Regeln — mise](https://app.so-mise.com/arbeitszeitgesetz-gastronomie)
- [Arbeitsrecht und Arbeitszeiten in der Gastronomie — DISH](https://www.dish.co/DE/de/blog/arbeitszeiten-in-der-gastronomie/)
- [§ 12 TzBfG – Arbeit auf Abruf — gesetze-im-internet.de](https://www.gesetze-im-internet.de/tzbfg/__12.html)
- [Constraint-Based Scheduling Algorithms — Shyft](https://www.myshyft.com/blog/constraint-based-scheduling/)
- [Fair Distribution Algorithms for Equitable Employee Scheduling — Shyft](https://www.myshyft.com/blog/fair-distribution-algorithms/)
- [Optimal Scheduling of Waitstaff with Different Experience Levels at a Restaurant Chain — INFORMS](https://pubsonline.informs.org/doi/10.1287/inte.2022.1124)
