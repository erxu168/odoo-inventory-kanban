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

Each restaurant defines its own **shift patterns** (Odoo already has these:
`planning.slot.template` — a start time, a duration, a role). Today you have
two. Another restaurant defines five. A café defines one. A hotel defines
"Early / Late / Night".

The staff-facing grid is generated *from* those patterns:

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

**Rogers' job afterwards** is: maintain the coverage matrix, maintain
per-person rules, set the weights, and approve. That is a ~30 minute/month job
instead of a full day, and it is a job a second manager can take over because
it is all on screen.

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
| H5 | Manager block: person X never on weekday Y / shift Z | per-person rule |
| H6 | Contract hour cap for the period | `hr.employee` |
| H7 | **Minijob earnings cap** — €603/month, 43.38 h at €13.90 (2026) | law + payroll |
| H8 | Max daily hours: 8h, 10h with 24-week averaging | ArbZG §3 |
| H9 | Min rest between shifts: 11h; gastronomy may cut to 10h **only if** compensated by a 12h rest within 4 weeks | ArbZG §5 |
| H10 | Max 6 working days per week, Sunday rest, ≥15 free Sundays/year | ArbZG §9/§11 |
| H11 | Minors: no work after 22:00, 8h/day, 5-day week | JArbSchG |
| H12 | Certification valid on the date (IfSG §43 hygiene, first aid) | employee record |
| H13 | Publication notice: roster published ≥4 days before the first shift | TzBfG §12(3) |

H7 deserves emphasis: it must be enforced in **euros**, not only hours,
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
| S3 | Fair share of *undesirable* shifts | see the credit ledger, §6 |
| S4 | Skill mix per shift ≥ threshold | not just headcount — see §5 |
| S5 | At least one keyholder / senior per shift | often better as hard |
| S6 | Schedule consistency week to week | hugely underrated; staff plan their lives around it, and familiar teams make fewer mistakes |
| S7 | No "clopening" (close then open next morning) | legal at 10h rest, still corrosive |
| S8 | Minimise split shifts | cap per person per week |
| S9 | Labour cost within the day's budget | see §5 |
| S10 | Pairing rules: A works well with B / never A with B | quiet but real |
| S11 | Guarantee ≥2 consecutive days off | retention |
| S12 | Guarantee N free weekends per period | retention |
| S13 | Prefer longer shifts for commuters | a 4h shift for a 50-min commute is a resignation letter |
| S14 | Minimise change vs the previous published version | so a re-run doesn't reshuffle everything |

S14 matters more than it looks. Once Rogers has hand-adjusted a draft, a re-run
must not throw his edits away. Pin manually-edited slots and re-optimise only
around them.

---

## 5. Parameters you did not ask about

You asked what else is out there. These are the ones that pay for themselves,
grouped by where they come from.

### Demand side — how many people do we actually need?

Right now the demand is implicit in Rogers' head. Make it a **coverage matrix**:
weekday × shift × role → headcount, with per-date overrides for holidays,
events, and closures. That alone removes half the manual work.

Then, later, the coverage can be *derived* rather than typed:

- **forecast covers / revenue per daypart** from POS history (same weekday,
  trailing weeks, plus year-over-year)
- **labour cost as % of forecast revenue** — the industry's actual control
  number; give each day a € budget and let the optimiser respect it
- **sales per labour hour** as the efficiency target
- local events, school holidays, weather (a beer garden's Saturday is a weather
  function), delivery-platform peak windows, reservation book

Start with the hand-typed matrix. Derive it in phase 4, when there is history.

### Shift composition — who is on together, not just how many

- minimum **skill points** per shift, not just headcount: three trainees is not
  the same as one senior plus two trainees
- never more than one new hire per shift; a trainee always with their trainer
  during the onboarding weeks
- exactly one shift lead / keyholder / cash-responsible person per shift
- language or station coverage (someone on the grill who can actually cook)
- first-aider present

### Data you already collect and are not using yet

This repository already tracks, per shift, **task completion score**
(`restaurant.task.list.completion_score`) and **attendance**
(`hr.attendance`, plus `avg_task_completion` on `hr.employee`). That is exactly
the raw material for a computed **reliability score**:

```
reliability = w1·avg_task_completion
            + w2·(1 − no_show_rate)
            + w3·(1 − late_check_in_rate)
            + w4·(1 − late_checkout_or_overrun_rate)
```

This directly answers your "certain people are slow or unreliable and should
not be on a Friday" case — but as a *measured, visible, arguable number*
instead of something the manager has to remember and defend. Then:

- mark Friday/Saturday as **high-demand** shifts with a minimum reliability
  threshold (a soft constraint with a high weight, or hard if you prefer)
- the block becomes automatic and self-correcting: someone whose scores improve
  earns their way back onto the strong days without anyone re-deciding
- keep a manual override on the employee record for the cases the data misses

Rolling 8–12 weeks, not lifetime, so a bad month is recoverable.

### Financial

- overtime avoidance (schedule to target, keep a buffer)
- Minijob cap alerting at 80% / 100% (H7)
- avoid accidentally pushing someone from Minijob into Midijob territory
- night premium hours (tax-free supplements after 20:00) as a cost input
- holiday and Sunday premiums

### Human factors

- blocked personal dates (a birthday, an exam) separate from ordinary
  availability, with a small annual quota so they stay meaningful
- students' exam periods
- last public transport → cannot take a closing shift
- seniority as a tiebreak only, never as a hard rule
- a "wants more hours" flag — the cheapest way to fill an open shift is to ask
  the person who has been asking for more

---

## 6. The fairness credit ledger

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

## 7. Explainability is a feature, not a nicety

An auto-generated roster that cannot explain itself will be overridden until it
is abandoned. Every run must record, per decision:

- for each assignment: which rules made this person the best fit
- for each **unfilled** slot: why nobody could take it — "3 candidates, 2 hit
  the monthly cap, 1 fails the 11h rest rule after Thursday's close"
- for each person: hours vs target, cap headroom, fairness credit, preference
  match rate

That last one is also what you show the staff member: *this* is why you got
these shifts. It is the difference between "the computer decided" and "here is
the arithmetic".

Unfilled slots should not block publication. Publish them as Odoo **open
shifts** — staff can claim them, which is a native Planning feature and the
natural pressure valve for a roster that is 95% solved.

---

## 8. Proposed data model

New models, following this repo's existing conventions
(`restaurant.*` prefix, `mail.thread` on the records that need a history):

| Model | Purpose |
|---|---|
| `restaurant.planning.period` | the window: date range, open/close datetimes, state, non-responder policy, generation weights |
| `restaurant.availability.request` | one per employee per period; state, submitted-on, quota check, portal token |
| `restaurant.availability.line` | `(date, time_from, time_to, preference)` — the storage format from §2 |
| `restaurant.coverage.rule` | weekday or date × shift template × role → headcount, min skill points, min reliability |
| `restaurant.schedule.rule` | typed per-employee or global constraint (blocked weekday, blocked shift, pairing, max consecutive days…) |
| `restaurant.schedule.run` | a generation attempt: score, log, violations, link to the created draft slots |
| `restaurant.fairness.ledger` | rolling credits per employee (§6) |

Extended:

| Model | Added |
|---|---|
| `hr.employee` | target/min/max hours per period, earnings cap (€) and hourly cost, skill level per role, reliability score (computed), max consecutive days, min rest override, commute/transport flag, minor flag, certifications, "wants more hours" |
| `planning.slot` | link to the generating run, undesirability weight, assignment reason, `is_pinned` (survives re-runs) |

Reused from Odoo, **not** rebuilt:

- `planning.slot` — the roster itself, with its Gantt view, publish & send,
  open shifts, and recurrence
- `planning.slot.template` — the shift patterns (§2)
- `planning.role` — roles and role-based eligibility
- `hr.leave` — approved time off feeds H2 for free
- `resource.calendar` — contractual working schedules

Odoo Planning already has an **Auto Plan** button that fills open shifts by
role, availability and hour limits. It is a reasonable baseline and worth a
look before writing anything — but it does not know about earnings caps,
skill mix, reliability, fairness credits, or a staff availability window, which
is precisely the gap this proposal fills.

*(Field names on the Odoo side should be verified against the installed
version before implementation — Planning's internals move between releases.)*

---

## 9. The engine

For a restaurant — roughly 15–30 staff, 60–120 slots a month — a **greedy
construction plus local-search repair** in plain Python is the right tool:

1. **Filter**: for every slot, compute the candidate set that passes all hard
   constraints. Slots with zero candidates are reported immediately.
2. **Order**: schedule the most constrained slots first (fewest candidates,
   highest coverage requirement). This is what makes greedy work.
3. **Score**: pick the candidate with the best weighted soft score.
4. **Repair**: local search — swap pairs of assignments while the total score
   improves, with a fixed iteration budget.
5. **Report**: score, per-assignment reasons, unfilled slots with causes.

Deterministic (fixed random seed) so the same inputs give the same roster —
"I re-ran it and got something different" destroys trust fast.

Keep the constraint checks as small, independently testable functions and the
weights as data. Then, if the restaurant grows past what heuristics handle
well, an OR-Tools CP-SAT backend can be swapped in behind the same interface
without touching the data model. Do not start there: CP-SAT is harder to
explain, harder to debug, and adds a dependency for a problem this size.

---

## 10. Rollout

Each phase is independently useful — if you stop after any of them, you are
still better off than today.

| Phase | Delivers | Value on its own |
|---|---|---|
| **1** | Periods, availability window, staff grid, reminders, quota rule. Rogers still assigns manually. | The data stops living in WhatsApp. Rogers has one screen instead of twelve conversations. |
| **2** | Coverage matrix + generator with **hard constraints only** → draft roster. | The legally-invalid and cap-breaking rosters become impossible. Most of the manual time disappears. |
| **3** | Soft objectives, weights, fairness ledger, explanations. | The roster stops merely being valid and starts being *good*, and defensible. |
| **4** | Reliability score from attendance + task data, demand forecast from POS, labour cost budget. | The system starts managing, not just scheduling. |

Phase 1 is worth building even if you never build phase 2.

---

## 11. Open questions for Rogers

1. **Period length** — calendar month (matches the Minijob cap cleanly) or
   4-week cycle (matches rest-period compensation cleanly)? Monthly is
   recommended; the cap is the tighter constraint.
2. **Window timing** — e.g. opens on the 1st, closes on the 20th, published on
   the 25th for the following month. Legal floor is 4 days' notice; 2–3 weeks
   is what staff actually need.
3. **Where do staff submit** — Odoo backend (they already have accounts for the
   task module) or a tokenised portal link (works for staff without a login)?
4. **Are the strong-day blocks hard or soft?** Hard is simpler to explain;
   soft means the roster can still be filled on a bad week.
5. **Which of the composition rules are hard?** "One keyholder per shift" is
   usually hard; "at least one senior" is usually soft.
6. **What is the current no-show / late rate?** It determines whether phase 4's
   reliability score is worth building or a solution in search of a problem.

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
