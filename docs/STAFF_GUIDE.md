# Krawings Staff Guide — Restaurant Tasks & Inventory Count

A step-by-step walkthrough of the two custom Odoo apps used on the floor:

- **Restaurant Tasks** — shift checklists, photo proof, sign-off, escalation
- **Inventory Count** — the mobile "Physical Inventory" counting screen

Each section is marked with who it is for: **Staff**, **Manager**, or **Admin**.

---

## 0. Before you start

### Logging in
1. Open the Odoo address on your phone, tablet, or the back-office PC.
2. Sign in with your own account. Never share logins: task sign-offs and inventory counts are recorded under the name that is logged in.
3. After login you land on the **Apps Home** screen ("Select an app to get started"). It shows one tile per app you have access to. Tap **Restaurant Tasks** or **Inventory**.
4. To get back to this screen at any time, tap the app-grid icon in the top-left corner of any Odoo page.

### Who sees what
| Role | Restaurant Tasks | Inventory |
|---|---|---|
| **Staff** | *My Tasks* only: the shift lists assigned to you | Count products, add missing products |
| **Manager** | Everything above, plus *Task Lists*, *All Tasks*, *Dashboard*, *Task Templates* for their own location | Everything above, plus **Apply All** to post the adjustments |
| **Owner / Admin** | Everything, all locations, plus *Escalation Rules* and the *Reset* buttons | Same as Manager |

If a menu described below is missing for you, your account simply does not have that role. Ask your manager.

### Phone tips
- Add the Odoo address to your home screen (Share → *Add to Home Screen* on iPhone, browser menu → *Add to Home screen* on Android). It then opens like an app.
- Turn the phone sideways on the task list screens if columns feel cramped. The inventory screen is designed for portrait.

---

# Part A — Restaurant Tasks

## A1. Staff: completing your shift checklist

### Step 1 — Open *My Tasks*
Tap **Restaurant Tasks → My Tasks**.

You see a board with four columns: **Draft**, **Active**, **Completed**, **Expired**. By default only *Active* lists are shown (the "Active" filter chip is on). Each card shows:

- your avatar and the list name, e.g. `Maria Lopez — Opening Shift Checklist — 2026-09-15`
- the shift date
- a green progress bar and the count of finished tasks, e.g. `3/7 tasks`

Tap the card for today's shift.

> **Nothing here?** Either no list has been generated for your shift yet (ask your manager), or your login is not linked to your employee record (ask the admin).

### Step 2 — Read the shift list
The list opens as a form. At the top you see a status bar **Draft → Active → Completed** and the shift details: template, planning shift, your name, location, shift start and end, the **Checkout Policy** (see Step 6), and your **Completion %**.

Under the **Tasks** tab, every task is a row:

| Column | Meaning |
|---|---|
| Name | The task |
| Completion Type | **Checkbox** (just mark it done) or **Photo Required** (you must upload a picture) |
| Deadline | When it must be done. Deadlines are counted from the shift start, e.g. "60 min after shift start" |
| Time remaining | Live text: `2h 15m left`, `Overdue 0h 30m`, `Completed`, or `No deadline` |
| Checklist % | Progress on the task's sub-items, if it has any |
| Status | **To Do**, **In Progress**, or **Done** |

Row colours: **red** = overdue, **green** = done.

### Step 3 — Do a simple checkbox task
For a task with no checklist and no photo:

1. Do the job.
2. Tap the green **✓ Done** button at the end of the row.
3. The row turns green, the status badge says **Done**, and your completion bar moves up.

### Step 4 — Do a task with a checklist or a photo
Tap the task name (not the button) to open the task screen. It has its own status bar **To Do → In Progress → Done** and these tabs:

- **Instructions** — the manager's notes on how to do the job (only shown when there are instructions).
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
- Overdue tasks can also be **escalated**: after a set delay an email and activity go to your manager, then to the next level. See A3.
- **Checkout policy**: if the checklist template is set to **Block Checkout**, Attendance will not let you check out until every task is done. The message is `Cannot check out: incomplete tasks with "Block Checkout" policy.` With **Show Warning** you can check out, but the incomplete score is recorded against your attendance.

### Fixing mistakes
- Marked a task done by accident? Ask a manager: only managers can **Reset** a task back to *To Do* (this also clears the photo and the checklist).
- Wrong shift list assigned to you? Tell your manager; they can reset or reassign it.

---

## A2. Manager: setting up and running shifts

### Step 1 — Build a checklist template (once)
Go to **Restaurant Tasks → Configuration → Task Templates → New**.

1. **Name** the template, e.g. *Opening Shift Checklist*, *Closing – Kitchen*, *Weekly Deep Clean*.
2. **Location** — pick your restaurant to restrict the template to it, or leave empty to use it everywhere.
3. **Checkout Policy** — **Show Warning** (default) or **Block Checkout** (staff cannot clock out until all tasks are done). Use Block only for lists you are sure staff can always complete.
4. Optional **Description** for your own notes.
5. In the **Tasks** table, tap *Add a line* for each task:
   - drag the handle on the left to reorder,
   - **Completion Type**: Checkbox or Photo Required,
   - tick **Has deadline** and set **Deadline (min after shift start)**, e.g. `30` means due 30 minutes after the shift begins,
   - the **Checklist** column shows how many sub-items the task has.
6. **Save**.

The template's chatter records who changed what. Untick **Active** to retire a template without deleting history.

> **Checklist sub-items** (the toggles staff see under a task) are not editable from this table; they are set up by the admin (see A3).

### Step 2 — Assign a shift list
Go to **Restaurant Tasks → Task Lists → New**.

1. Pick the **Template**, the **Employee**, and the **Location**.
2. Set **Shift Start** and **Shift End**. Deadlines are calculated from *Shift Start*, so set it correctly.
3. Optionally link the **Planning Shift** from the Planning app.
4. **Save**, then tap **Generate Tasks** in the header.

Generate Tasks copies every task and sub-item from the template onto this list, calculates the deadlines, and sets the list to **Active**. The list now appears on the employee's *My Tasks* board. The list name is built automatically: `Employee — Template — date`.

Create one list per employee per shift. A Planning shift can carry several lists; its form shows a **Task Lists** smart button once any exist.

### Step 3 — Monitor during the shift
**Task Lists** (list, board, or form view) shows every list for your location with employee, template, shift start, `done/total`, progress bar, and status. Filters at the top: **Active**, **Completed**, **Expired**, **Today**, **This Week**; group by **Employee**, **Location**, **Status**, or **Shift Date**.

**All Tasks** lists every individual task. Filters: **Overdue**, **To Do**, **Done**. You can tap **✓ Done** here to close a task on someone's behalf, and open a task to **Reset** it.

**Dashboard**:
- **Today's Overview** — bar chart of today's tasks per employee, split by status.
- **Weekly Trends** — line chart of average completion % per day since Monday.
- **Overdue Tasks** — plain list of everything currently past its deadline.

### Step 4 — Fix problems
| Situation | What to do |
|---|---|
| Task marked done by mistake | Open the task → **Reset**. Photo and checklist are cleared. |
| Wrong employee or template on a list | Owner/Admin taps **Reset** on the list (back to Draft, all tasks removed), edit, then **Generate Tasks** again. |
| Staff cannot clock out | Check the list's tasks; either complete/reset them, or change the template's checkout policy to *Show Warning* for next time. |
| Employee sees nothing in *My Tasks* | Their user is not linked to the employee record (Employees → employee → HR Settings → Related User). |

### Step 5 — Where the scores show up
- **Attendance** record: a *Task Completion* section with the completion % and whether checkout is blocked. The attendance list has an optional *Task Completion %* column (enable it from the column picker).
- **Employee** form: an **Avg Completion** smart button opens all their task lists grouped by employee.
- **Planning** shift: a **Task Lists** smart button.

---

## A3. Admin: rules, access, and maintenance

### Escalation rules
**Restaurant Tasks → Configuration → Escalation Rules** (Owner/Admin only). Each rule is one level of the chain:

| Field | Meaning |
|---|---|
| Level | 1, 2, 3 — evaluated in order |
| Delay After Overdue (min) | How long after the deadline this level fires |
| Recipient | Assigned Employee, Department Manager, Employee's Manager, or a Specific Employee |
| Send Email | Also send the "🚨 Escalation Level N — Overdue Task" email to the recipient's work email |
| Active | Untick to pause the rule |

Example chain: Level 1 at +0 min → assigned employee; Level 2 at +30 min → Employee's Manager; Level 3 at +90 min → Specific Employee (the owner). The escalation job runs every 5 minutes; each level fires once per task.

### Access rights
Settings → Users → open the user → under **Restaurant Tasks** choose **Staff**, **Manager**, or **Owner / Admin**.

- **Staff** see only lists where the employee's *Related User* is them, so every staff account must be linked to its employee record.
- **Managers** see only lists whose location matches the **Work Location** on *their own* employee record. A manager with no work location sees nothing in *Task Lists*.
- **Owner / Admin** sees everything.

### Checklist sub-items on templates
Sub-items (the toggles under a task) live on the individual task template. The Task Templates screen only shows their count. To edit them, enable developer mode (Settings → *Activate the developer mode*), open the task template record, and add lines under **Checklist Items**. Consider asking the developer to add an open-form button to the tasks table.

### Scheduled jobs and emails
Two scheduled actions run automatically (Settings → Technical → Scheduled Actions): *Restaurant Tasks: Check Overdue* (every 10 min) and *Restaurant Tasks: Escalation Chain* (every 5 min). Outgoing email must be configured for escalation emails to leave the server.

---

# Part B — Inventory Count

## B1. Staff: counting stock on your phone

### Step 1 — Open the counting screen
**Inventory → Operations → Adjustments → Mobile View: Physical Inventory**.

The screen has:

- a header **Physical Inventory** with **Refresh** and **Apply All** (Apply All is for managers, see B2),
- a **Search product…** box and a **Location** dropdown (starts on *All Locations*),
- three chips: **Total** (products matching the search/location), **Counted**, **Differences**,
- one **card per product per location**, 20 at a time with a **Load More** button at the bottom,
- a round **+** button bottom-right to add a product that is not on the list.

### Step 2 — Pick the location you are counting
Choose your area in the **Location** dropdown (e.g. *Kitchen/Dry Store*, *Bar/Fridge 1*). The list reloads with only that location's products. Always count one location at a time; it keeps the list short and makes Apply All safe.

Use **Search** to jump to a product by name. It searches the product name only, not the reference code.

### Step 3 — Read a card
Each card shows:

- the product **category** in small caps, the **product name**, its **reference code** (barcode icon) and **lot** if any, and a **location** badge on the right,
- **On Hand** — what Odoo thinks is there,
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

Counts are saved to Odoo the moment you confirm, so several people can count different locations at the same time. Tap **Refresh** to pull in what others have entered.

### Step 5 — Correct a mistake
Tap the count field again, enter the right number, **Confirm Count**. The new value replaces the old one. Nothing is final until a manager applies the adjustment (B2).

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

## B2. Manager: reviewing and applying the count

1. Open the same screen and select the **Location** that was counted.
2. Scan the cards. The **Differences** chip tells you how many loaded cards disagree with the system; red-tinted cards are shortages, green-tinted are surpluses. Tap **Load More** until all cards are loaded.
3. Investigate anything surprising before applying: recount, check the bin next door, check for a pending transfer.
4. Tap **Apply All**. A yellow banner asks *This will apply all inventory adjustments and create stock moves. Are you sure?* Tap **Yes**.
5. The toast `Inventory adjustments applied!` confirms. Odoo posts stock moves for every difference; on-hand quantities now equal the counts, counted values reset to 0, and the cards reload.

**Important**

- Apply All acts on the **location selected in the dropdown**. With *All Locations* selected it applies every internal location in the warehouse at once. Always select the location first.
- Applying is not undoable from this screen. The moves it creates are visible under **Inventory → Reporting → Moves History** (source or destination *Inventory adjustment*), and a wrong count must be fixed by counting again and applying again.
- Apply All requires the **Inventory / Administrator** access right.

The same counts also appear in the standard **Inventory → Operations → Physical Inventory** list, so you can review them there with Odoo's usual filters and history.

---

## B3. If your counting screen looks different

The repository also contains three other versions of the counting screen (*Physical Inventory (Kanban)*, *Inventory Count (Pro)* under Inventory → Operations, and a standalone tablet app at `/inventory-count`). They use the same numpad drawer and the same rules, with a two-column layout instead of a single list:

- Left column **To Count**, right column **Counted**. A card moves right once you confirm.
- A progress bar at the top (`14 / 40 counted`).
- A **✓ Match** button directly on each card, so a matching shelf takes one tap.
- Coloured stripe and chip on each card: grey **Pending**, green **✓ Match**, blue **+2.00 over**, red **1.00 short**.
- Tabs **All / To Count / Done** and a search box (Pro and standalone); a **Location** dropdown (standalone only).
- **Validate** in the header is the manager's Apply All. In the standalone app it asks *Validate inventory and apply all adjustments?* and applies **every counted product in every location**, so finish all locations before validating there.

---

# Part C — Quick reference

### Status colours, Restaurant Tasks
| Where | Colour / badge | Meaning |
|---|---|---|
| Task list card or row | grey | Draft — not generated yet |
| | orange / yellow | Active — in progress |
| | green | Completed |
| | red | Expired |
| Task row | red text | Overdue |
| | green text | Done |
| Task status badge | blue | In Progress |
| | green | Done |

### Status colours, Inventory Count
| Colour | Meaning |
|---|---|
| No badge | Not counted yet, or count equals on-hand |
| Green badge / tint | Counted more than the system expects |
| Red badge / tint | Counted less than the system expects |

### Frequently asked
**I completed everything but the list still says Active.** Tap **Sign Off Shift** in the header (signature must be saved first).

**The ✓ Done button says a photo is required.** Open the task, go to *Photo Proof*, upload the picture, then *Mark Done*.

**I cannot clock out.** One of your lists uses *Block Checkout* and still has open tasks. Finish them or ask a manager to reset them.

**My count disappeared.** A manager applied the adjustment, so on-hand now equals your count and the counted field reset. Check *On Hand*.

**The screen will not scroll on my iPhone.** Known Odoo issue after an update. Tell the admin (see below).

### Admin maintenance note
After **every Odoo 19 update** the admin must re-apply the iOS scroll fix on the server (see the repository README): patch `webclient_layout.scss`, clear the `web.assets` attachments, and restart the Odoo service. Without it the mobile screens do not scroll on iPhone and iPad.

The **WAJ BoM Mobile Fix** module only tidies the Manufacturing → Bills of Materials screens on phones (hides the Reference, Type, Company, and Unit columns by default; use the column picker to show them). It has no workflow of its own.
