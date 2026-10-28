"""Data model: what we extract from every grocery bill."""
from typing import List, Optional
from pydantic import BaseModel, Field

CATEGORIES = [
    "Produce", "Dairy & Eggs", "Meat & Fish", "Bakery", "Pantry",
    "Frozen", "Beverages", "Snacks & Sweets", "Household", "Personal Care", "Other",
]


class LineItem(BaseModel):
    name: str = Field(description="Product name, cleaned of codes where possible")
    quantity: float = Field(default=1, description="Units or weight purchased")
    unit_price: Optional[float] = Field(default=None, description="Price per unit, if printed")
    total_price: float = Field(description="Line total after quantity; negative for item-level discounts")
    category: str = Field(default="Other", description=f"One of: {', '.join(CATEGORIES)}")


class Bill(BaseModel):
    store_name: Optional[str] = None
    store_address: Optional[str] = None
    date: Optional[str] = Field(default=None, description="Purchase date as YYYY-MM-DD")
    currency: Optional[str] = Field(default=None, description="ISO code or symbol, e.g. EUR, USD, INR")
    items: List[LineItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    discount: Optional[float] = Field(default=None, description="Total bill-level discount as a positive number")
    total: Optional[float] = Field(default=None, description="Final amount paid")
    payment_method: Optional[str] = None
