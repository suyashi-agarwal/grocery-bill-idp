"""Step 2: sanity-check extracted numbers so errors get flagged, not silently saved."""
from schema import Bill

TOL = 0.05


def validate_bill(b: Bill) -> list[str]:
    warnings = []
    if not b.items:
        return ["No items were found on this bill."]

    items_sum = round(sum(i.total_price for i in b.items), 2)

    for i in b.items:
        if i.unit_price is not None and abs(i.quantity * i.unit_price - i.total_price) > TOL * max(1, i.quantity):
            warnings.append(f"'{i.name}': {i.quantity} x {i.unit_price} does not equal {i.total_price}.")

    if b.subtotal is not None and abs(items_sum - b.subtotal) > TOL:
        warnings.append(f"Items add up to {items_sum}, but the bill's subtotal is {b.subtotal}.")

    if b.total is not None:
        base = b.subtotal if b.subtotal is not None else items_sum
        disc = abs(b.discount or 0)
        # Some countries print prices with tax included, so accept both interpretations.
        candidates = {round(base - disc, 2), round(base + (b.tax or 0) - disc, 2)}
        if all(abs(b.total - c) > TOL for c in candidates):
            warnings.append(f"Total {b.total} doesn't match items/tax/discount (expected one of {sorted(candidates)}).")

    if not b.date:
        warnings.append("No date found; please enter one before saving.")
    if not b.store_name:
        warnings.append("No store name found.")
    return warnings
