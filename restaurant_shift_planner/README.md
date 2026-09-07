# Restaurant Shift Planner — Attributes & Requirements

Phase 1 of [the automated shift planning design](../docs/planning-automation-design.md).

Staff carry **attributes**. Shift templates declare **requirements** over those
attributes. One routine matches the two, and three surfaces use it.

This phase deliberately does not schedule anything. It makes manual planning
safe, and tells the manager where the gaps are while there is still time to do
something about them.

## What it adds

| Menu | What it is for |
|---|---|
| Shift Planning → Staff → Attribute Values | What each person can do, with validity dates |
| Shift Planning → Staff → Expiring & Overdue | Certificates about to lapse, values gone stale |
| Shift Planning → Checks → Coverage Gap Report | Which shifts in a date range cannot be staffed |
| Shift Planning → Configuration → Staff Attributes | Define the attributes themselves |
| Shift Planning → Configuration → Shift Requirements | Define what each shift needs |

Plus a **Shift Attributes** page on the employee form, and a live requirement
check on the Planning shift form that warns the moment someone unsuitable is
assigned.

## Writing a requirement

Every rule below is a data row. None of them needed a code change.

| Rule | Scope | Measured as | Operator | Value | Count |
|---|---|---|---|---|---|
| Everyone must be hygiene-certified | Every person | — | Must be valid | — | — |
| Nobody below service speed 2 | Every person | — | At least | 2 | — |
| At least one keyholder on shift | Crew | Number of people | Must have | — | at least 1 |
| At least two who can run the grill at 4+ | Crew | Number of people | At least | 4 | at least 2 |
| Crew average speed at least 3.5 | Crew | Crew average | At least | 3.5 | — |
| At most one person still learning the grill | Crew | Number of people | At most | 0 | at most 1 |
| Fri/Sat only: everyone reliability ≥ 70 | Every person | — | At least | 70 | — (tick Fri, Sat) |

The two scopes are both necessary. A per-person rule cannot express "one
keyholder"; a crew rule cannot express "nobody without hygiene training".

A requirement with **no shift template** applies to every shift — that is how a
house rule gets written once. A requirement with a **role** applies only to
slots being filled for that role.

## Things worth knowing

**Crew means overlap, not template.** Planning stores one slot per person, so
the crew for a rule is everyone whose shift overlaps. That is what makes "one
keyholder on shift" work when the keyholder is behind the bar and the rule sits
on the service template.

**Values are dated, not overwritten.** To change a level, end the current value
and add a new one. Overwriting means last month's roster can no longer be
explained, and a certificate's validity on a given day can no longer be proved.
The form's *End As Of Today* button does this correctly.

**Expiry needs no special case.** Attribute lookups are filtered to the shift's
date, so a lapsed certificate is simply absent, and every requirement that
depends on it fails on its own. A daily cron raises an activity before a
certificate lapses, because nobody tracks these by hand for long.

**A missing value reads as zero.** Someone with no recorded grill level fails
"grill at least 1". That is deliberate: an unrecorded skill is not a permission.

**Attributes that nothing references are dead weight.** The attribute form shows
how many requirements use it, and the search view has a *Not Used By Any
Requirement* filter. Ten or so attributes is the right size.

## Deliberately not shipped

The starter data has no *reliability* or *tenure* attribute. Those are worth
having once they are computed from attendance and task-completion data
(phase 4). A hand-typed reliability score is exactly the subjective judgement
this module exists to replace.

## Tests

```
odoo -d <db> -u restaurant_shift_planner --test-enable --test-tags /restaurant_shift_planner
```

Covers threshold and certification tests, crew count minimums and maximums,
crew averages, weekday and date filtering, candidate filtering, the
no-overlapping-values rule, and the end-to-end slot check including the
overlap-based crew.

## Next

Phase 2 adds the coverage matrix (weekday × shift × role → headcount) and the
generator. The generator calls the same evaluation routine used here, so the
draft roster and the manual warnings can never disagree about who is suitable.
