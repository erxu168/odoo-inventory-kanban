# Restaurant Daily Sales (`restaurant_sales`)

Odoo 19 · depends on `point_of_sale`

One record per outlet per business day. The entry pulls its figures straight
from Point of Sale and asks the closing staff to declare what they actually
counted, so every shortage or overage is visible and explained before a manager
signs it off.

## The business day, not the calendar day

A shift that starts on Friday evening and rings its last order at 02:30 is one
day's trading, not two. Each outlet has a **business day cutoff** (default
04:00) and a **sales timezone**; the entry for the 25th covers
`25/04:00 → 26/04:00` local time. Both boundaries are localized separately, so
a DST switch inside the window still lands on the cutoff hour.

The timezone is stored on the outlet rather than read from the user, because
the nightly scheduled action runs as a system user with no timezone of its own.

## Workflow

```
draft ──submit──> submitted ──approve──> approved
  ^                    │
  └──── send back ─────┘  (rejected → editable again)
```

* **Draft** entries are opened automatically for every outlet once its business
  day ends (`Restaurant Sales: Open Yesterday's Entries`, hourly and
  idempotent). Creating one by hand closes a day out early.
* **Submit** is blocked while the cash variance exceeds the outlet's tolerance
  and no explanation has been written.
* **Approve** is a manager action; **Send Back** requires a reason and notifies
  the person who closed the day.
* Approved entries cannot be deleted without being reset to draft first.

## What comes from POS, and what is typed

| From Point of Sale (read-only) | Typed at close-out |
| --- | --- |
| Orders, refunds, taxes, net sales | Counted amount per payment method |
| Amount taken per payment method | Cash counted |
| Opening float, sessions | Variance explanation, shift notes |
| — | Off-POS channel revenue |

POS figures are read with `sudo()`: the staff reconciling a till are not given
back-office POS access, but the numbers they reconcile against must be the real
ones. Refreshing never overwrites a counted amount, and a payment method that
was retired mid-day keeps its line as long as money was declared against it.

## Off-POS channels

Delivery platforms, catering and event revenue never touch the terminal.
Each channel carries a default commission; every daily line records gross,
commission and net payout, and feeds the **Channel Mix** report.

## Access

Three groups under the *Restaurant Sales* privilege: **Staff**, **Manager**,
**Owner / Admin**. Visibility is driven by the outlet, not by the record's
author — nightly entries have nobody assigned, so each outlet lists its
**Close-out Staff** and **Approvers** (Configuration → Outlets). Admins see
every outlet; a global rule keeps companies apart.

## Configuration

Configuration → Outlets, per point of sale:

| Setting | Default | Meaning |
| --- | --- | --- |
| Daily Sales Entry | on | Open a draft entry every night |
| Sales Timezone | user's | Which day an order belongs to |
| Business Day Cutoff | 04:00 | When the day rolls over |
| Cash Variance Tolerance | 5.00 | Above this, an explanation is mandatory |
| Close-out Staff / Approvers | — | Who sees and who approves |

These live on their own `pos.config` views rather than in an inherited Point of
Sale form: the stock POS form is restructured between versions, and an xpath
into it would turn a POS upgrade into a failed install.

## Install

```bash
# copy restaurant_sales/ into the addons path, then
odoo -u restaurant_sales -d <database>
```
