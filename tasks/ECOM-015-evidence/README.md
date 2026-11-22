# ECOM-015: Test evidence

| Field | Value |
|---|---|
| Tickets | [ECOM-015](../ECOM-015.md): Purchase UI, tested together with [ECOM-013](../ECOM-013.md) and [ECOM-014](../ECOM-014.md) |
| Test type | Manual acceptance test (owner), in the browser |
| Tester | Project owner |
| Date | 2026-11-22 |
| Environment | Local compose stack, shop at http://localhost:3000, build of `feature/ECOM-015-purchase-ui` with the code review round 3 fixes (D-099), database on migration 0008 |
| Result | **Passed**: no defects; observations deferred to [ECOM-018](../ECOM-018.md) |

## Test runs

| # | Step | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 1 | Add Backpack and Collar gift, open the cart | Prices and subtotal from the shop; the gift at $0.00 | Backpack $64.99, Collar gift $0.00, **Subtotal: $64.99**, **Go to checkout** enabled | **Passed** (ECOM-015 criterion 1, ECOM-013 criterion 1) | [01](01-cart-prices-from-the-shop.png) |
| 2 | Type 600 as the Backpack quantity | The line is flagged with what is available; checkout disabled | "Only 90 left." with **Use 90**; **Go to checkout** disabled; "Fix the items marked above before checking out." | **Passed** (stock never oversold, D-072) | [02](02-quantity-above-stock.png) |
| 3 | Check out with card 4242 4242 4242 4242, 12/30 | The summary from the shop; **Pay $64.99** | Summary 1 × Backpack $64.99, 1 × Collar gift $0.00, Total $64.99; the test cards shown under the field | **Passed** | [03](03-checkout-form.png) |
| 4 | **Pay $64.99** | The confirmation; stock taken; card's last 4 only | "Thank you, …", "Your order is paid.", both lines, Total $64.99, "card ending in 4242", the order number and a `fake_…` payment reference | **Passed** (ECOM-015 criterion 1, ECOM-013 criterion 3) | [04](04-confirmation-paid.png) |
| 5 | Air Purifier with card 4000 0000 0000 0002 | A clear decline; card cleared; details kept; nothing taken | "Your card was declined. Nothing was charged and nothing was taken from stock. Try another card."; card fields empty; name and email kept | **Passed** (ECOM-015 criterion 3, ECOM-013 criterion 2) | [05](05-declined-card.png) |
| 6 | Pay the Air Purifier again with 4242 | Paid with a new attempt | A second, paid order (database check below) | **Passed** | database |

**Owner's verdict:** "you can commit and go to next one".

**Database check after the test:**
- 3 orders: $64.99 `PAID` (4242), $189.99 `PAYMENT_FAILED` (0002), then $189.99 `PAID` (4242).
- Stock: Backpack 90 → 89, Collar gift 20 → 19, Air Purifier 20 → 19. The declined order took nothing.
- The audit log has one `order.paid` or `order.payment_failed` entry per order, and one `product.stock_decreased` entry per paid line, all by "Shop checkout" and each naming its order.

## Observations (deferred to ECOM-018, UI polish)

- **OBS-07, a subtotal of $0.00 next to a flagged line is confusing** (screenshot 02). The subtotal counts only the lines that can be bought, so 600 Backpacks ($38,994.00) next to "Subtotal: $0.00" reads oddly. Better: show the flagged line's total greyed out, and label the subtotal "Subtotal of available items", or hide it until the cart is fixed.
- **OBS-08, the browser disables card autofill over plain HTTP** (screenshot 03): "O preenchimento automático das formas de pagamento está desativado porque este formulário não usa uma conexão segura." This is expected on http://localhost. A real deployment needs HTTPS (ECOM-016 hardening and the README), and nothing should change in the app.
- **OBS-09, the expiry placeholder looks like a filled value** (screenshot 05). After a decline the fields are cleared, but the grey "12/30" placeholder can be mistaken for a kept value. Use "MM/YY" as the placeholder.
- **OBS-10, the quantity spinner appears only on hover** (screenshot 01, the browser's default number input). The quantity field could get explicit − and + buttons.
