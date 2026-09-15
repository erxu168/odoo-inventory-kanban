# WAJ Lunch Hour Discounts

Adds a **Limit to Days & Hours** option to pricelist rules so a discount can be
active only in a time window, for example a lunch deal on all dishes
**Monday to Friday, 12:00 to 16:00**.

The window is enforced everywhere the pricelist is used:

* **Point of Sale** – the check runs locally in the POS against the rule's
  timezone, so the discount switches on and off during an open session
  without reloading.
* **Backend** – sales orders, quotations and any other price computation
  through the pricelist use the order date/time.

## Setup: lunch deal on dishes, Mon–Fri 12–16h

1. Make sure your dishes share a product category (e.g. *Dishes*), or set the
   rule up per product instead.
2. Go to **Point of Sale ▸ Products ▸ Pricelists** (or **Sales ▸ Products ▸
   Pricelists**) and open the pricelist that your POS uses
   (*Point of Sale ▸ Configuration ▸ Point of Sale ▸ Pricing ▸ Default Pricelist*).
3. Add a rule:
   * **Apply To**: Category → *Dishes*
   * **Price Type**: Discount → e.g. `20 %`
   * Tick **Limit to Days & Hours**
   * **Hours**: `12:00` to `16:00`, **Days**: Mon–Fri (the default), and
     check the **Timezone** is the restaurant's.
4. Save. Outside the window the rule is ignored and the normal price applies.

If the discount should also apply to walk-in customers with a different
pricelist, add the same rule to that pricelist too.

## Notes

* The start hour is inclusive and the end hour exclusive: 12:00:00 is lunch,
  16:00:00 is not.
* A time-limited rule that is active wins over an everyday rule of the same
  level (product / category / all products). A product-specific rule still
  beats a category-level lunch rule, as in standard Odoo.
* Windows cannot cross midnight (start must be before end). For a late-night
  deal create two rules, e.g. 22:00–24:00 and 00:00–02:00.
* Order lines get their price when they are added. A line added at 11:58
  keeps the full price even if the order is paid at 12:05; the POS product
  grid refreshes its displayed prices on the next re-render (e.g. changing
  category or order).
