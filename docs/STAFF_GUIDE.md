# Krawings Staff Guide — Shift Checklists & Stock Counting

A step-by-step walkthrough of the two screens you use on the floor:

- **Restaurant Tasks** — your shift checklist, photo proof, and sign-off
- **Inventory Count** — the mobile "Physical Inventory" counting screen

---

## 0. Before you start

1. Open the Odoo address on your phone, tablet, or the back-office PC.
2. Sign in with **your own** account. Never share logins: sign-offs and stock counts are recorded under whoever is logged in.
3. After login you land on the **Apps Home** screen ("Select an app to get started"). Tap **Restaurant Tasks** or **Inventory**.
4. To get back to this screen at any time, tap the app-grid icon in the top-left corner of any Odoo page.

**Put it on your home screen.** iPhone: Share → *Add to Home Screen*. Android: browser menu → *Add to Home screen*. It then opens like an app.

If a menu described below is missing for you, ask your manager to check your account.

---

# Part A — Your shift checklist

### Step 1 — Open *My Tasks*
Tap **Restaurant Tasks → My Tasks**.

You see a board with four columns: **Draft**, **Active**, **Completed**, **Expired**. By default only *Active* lists are shown (the "Active" filter chip is on). Each card shows:

- your avatar and the list name, e.g. `Maria Lopez — Opening Shift Checklist — 2026-09-15`
- the shift date
- a green progress bar and the count of finished tasks, e.g. `3/7 tasks`

Tap the card for today's shift.

> **Nothing here?** Your shift list has not been created yet, or your login is not linked to your employee record. Ask your manager.

### Step 2 — Read the shift list
The list opens as a form. At the top you see a status bar **Draft → Active → Completed** and the shift details: your name, location, shift start and end, the **Checkout Policy** (see Step 6), and your **Completion %**.

Under the **Tasks** tab, every task is a row:

| Column | Meaning |
|---|---|
| Name | The task |
| Completion Type | **Checkbox** (just mark it done) or **Photo Required** (you must upload a picture) |
| Deadline | When it must be done |
| Time remaining | Live text: `2h 15m left`, `Overdue 0h 30m`, `Completed`, or `No deadline` |
| Checklist % | Progress on the task's sub-items, if it has any |
| Status | **To Do**, **In Progress**, or **Done** |

Row colours: **red** = overdue, **green** = done.

### Step 3 — Do a simple checkbox task
1. Do the job.
2. Tap the green **✓ Done** button at the end of the row.
3. The row turns green, the status badge says **Done**, and your completion bar moves up.

### Step 4 — Do a task with a checklist or a photo
Tap the task name (not the button) to open the task screen. It has its own status bar **To Do → In Progress → Done** and these tabs:

- **Instructions** — notes on how to do the job (only shown when there are some).
- **Checklist** — one toggle per sub-item. Flip each toggle as you finish; the checklist progress bar fills up. **All toggles must be on** before the task can be marked done.
- **Photo Proof** — only for *Photo Required* tasks. Tap the image box, take or choose a photo (e.g. the cleaned grill, the fridge thermometer), and it uploads.
- **Comment** — optional note for your manager ("Dishwasher leaking again, used the small one").

Then tap **Start** (optional, shows you are on it) and **Mark Done**.

If something is missing you get a clear message and the task stays open:

- `Task "Clean fryer" requires a photo.` → go to the Photo Proof tab and add a picture.
- `All checklist items must be completed for task "Close bar".` → flip the remaining toggles.

Use the **back arrow** (breadcrumb at the top) to return to the shift list.

### Step 5 — Sign off your shift
1. On the shift list, open the **Sign-Off** tab (it appears once the list is Active).
2. Draw your signature in the box with your finger. Tap **Save**.
3. Finish any remaining tasks.
4. When the last task is done, the list moves to **Completed** automatically. If it still shows *Active*, tap **Sign Off Shift** in the header.

Sign-off refuses with a message if the signature is missing (`Please provide your digital signature before signing off.`) or tasks are still open (`2 task(s) still incomplete…`).

### Step 6 — What happens if you are late
- Every 10 minutes the system checks deadlines. An overdue task creates a **To-Do activity** on your shift list (the clock icon in the chatter and the activity bell at the top of Odoo).
- Overdue tasks are also **escalated**: after a set delay your manager is notified, then the next person up.
- **Checkout policy**: if your checklist is set to **Block Checkout**, Attendance will not let you clock out until every task is done. The message is `Cannot check out: incomplete tasks with "Block Checkout" policy.` With **Show Warning** you can clock out, but the incomplete score is recorded against your attendance.

### Fixing mistakes
- Marked a task done by accident? Tell your manager: only they can reset a task back to *To Do* (this also clears the photo and the checklist).
- Wrong shift list assigned to you? Tell your manager.

---

# Part B — Counting stock on your phone

### Step 1 — Open the counting screen
**Inventory → Operations → Adjustments → Mobile View: Physical Inventory**.

The screen has:

- a header **Physical Inventory** with a **Refresh** button (ignore **Apply All**; it is for managers and will refuse you),
- a **Search product…** box and a **Location** dropdown (starts on *All Locations*),
- three chips: **Total**, **Counted**, **Differences**,
- one **card per product per location**, 20 at a time with a **Load More** button at the bottom,
- a round **+** button bottom-right to add a product that is not on the list.

### Step 2 — Pick the location you are counting
Choose your area in the **Location** dropdown (e.g. *Kitchen/Dry Store*, *Bar/Fridge 1*). The list reloads with only that location's products. Count one location at a time.

Use **Search** to jump to a product by name. It searches the product name only, not the reference code.

### Step 3 — Read a card
Each card shows:

- the product **category** in small caps, the **product name**, its **reference code** (barcode icon) and **lot** if any, and a **location** badge on the right,
- **On Hand** — what the system thinks is there,
- **Counted** — what has been entered so far,
- a wide **count field** ("Tap to count…" or the current count with a pencil),
- once counted, a **difference badge**: `+2 Units difference` (green tint) or `-1.5 kg difference` (red tint).

### Step 4 — Count a product with the numpad
1. Tap the count field. A drawer slides up from the bottom with the product name and location, and a big **Counted qty** display next to **Expected** and a live **Diff**.
2. Type the number on the numpad. Use **·** for decimals and the **←** key to delete. The Diff updates as you type.
3. Shortcuts above the numpad:
   - **✓ Match (12)** — fills in exactly the expected quantity. Use it when the shelf matches the system.
   - **0.00** — nothing left.
   - **Clear** — start the entry again.
4. Tap **Confirm Count**. The drawer closes, the card updates, and a small toast confirms: `Tomatoes — ✓ Match` or `Tomatoes — +2.00 difference`.
5. Not sure yet? Tap **Skip** (or the ✕, or outside the drawer). Nothing is saved and you can come back later.

Counts are saved the moment you confirm, so several people can count different locations at the same time. Tap **Refresh** to pull in what others have entered.

### Step 5 — Correct a mistake
Tap the count field again, enter the right number, **Confirm Count**. The new value replaces the old one. Nothing is final until your manager applies the count.

### Step 6 — Add a product that is not listed
If you find stock that has no card (new product, or it is in the wrong location):

1. Tap the round **+** button.
2. Choose the **Location**.
3. Type at least two letters of the **Product** name and pick it from the suggestions.
4. Enter the **Counted Quantity** and tap **Save**.

A card is created (or, if the product already had a card there, its count is updated) and the toast says `Product added to inventory!`.

### Step 7 — Finish
When every card in your location shows a counted value, tell your manager. Do **not** press Apply All; if you try, you will simply get `Access denied. Only stock managers can apply inventory adjustments.`

---

## If your counting screen looks different

Some devices use a two-column version of the counting screen (*Physical Inventory (Kanban)*, *Inventory Count (Pro)*, or the tablet app). Same numpad, same rules:

- Left column **To Count**, right column **Counted**. A card moves right once you confirm.
- A progress bar at the top (`14 / 40 counted`).
- A **✓ Match** button directly on each card, so a matching shelf takes one tap.
- Coloured stripe and chip on each card: grey **Pending**, green **✓ Match**, blue **+2.00 over**, red **1.00 short**.
- Tabs **All / To Count / Done** and a search box; a **Location** dropdown on the tablet app.
- Leave the **Validate** button to your manager.

---

# Quick reference

### Colours, shift checklist
| Where | Colour / badge | Meaning |
|---|---|---|
| Shift list card or row | grey | Draft — not started yet |
| | orange / yellow | Active — in progress |
| | green | Completed |
| | red | Expired |
| Task row | red text | Overdue |
| | green text | Done |
| Task status badge | blue | In Progress |
| | green | Done |

### Colours, stock count
| Colour | Meaning |
|---|---|
| No badge | Not counted yet, or count equals on-hand |
| Green badge / tint | Counted more than the system expects |
| Red badge / tint | Counted less than the system expects |

### Frequently asked
**I completed everything but the list still says Active.** Tap **Sign Off Shift** in the header (signature must be saved first).

**The ✓ Done button says a photo is required.** Open the task, go to *Photo Proof*, upload the picture, then *Mark Done*.

**I cannot clock out.** Your list uses *Block Checkout* and still has open tasks. Finish them or ask your manager.

**My count disappeared.** Your manager applied the count, so on-hand now equals what you counted and the counted field reset. Check *On Hand*.

**The screen will not scroll on my iPhone.** Known issue after an Odoo update. Tell your manager.
