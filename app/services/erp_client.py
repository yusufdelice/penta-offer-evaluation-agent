import json
from pathlib import Path
from typing import Dict, Any

STOCK_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "stock.json"
PRICES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "prices.json"


class ERPClient:
    """
    ERP Client adapter.
    Reads inventory and pricing records from 'data/stock.json' and 'data/prices.json'
    and calculates net margin based on requested discounts.
    """

    def __init__(self, stock_path: Path = STOCK_FILE, prices_path: Path = PRICES_FILE):
        self.stock_path = Path(stock_path)
        self.prices_path = Path(prices_path)
        self.stocks: Dict[str, Dict[str, Any]] = {}
        self.prices: Dict[str, Dict[str, Any]] = {}
        self.load_data()

    def load_data(self) -> None:
        """Loads stock.json and prices.json files."""
        if not self.stock_path.exists():
            raise FileNotFoundError(f"ERP stock data file not found: {self.stock_path}")

        if not self.prices_path.exists():
            raise FileNotFoundError(f"ERP price data file not found: {self.prices_path}")

        with open(self.stock_path, "r", encoding="utf-8") as f:
            self.stocks = json.load(f)

        with open(self.prices_path, "r", encoding="utf-8") as f:
            self.prices = json.load(f)

    def get_product_data(self, product_id: str, requested_discount: float = 0.0) -> Dict[str, Any]:
        """
        Returns stock quantity and net profit margin for a product based on requested discount.
        Returns {'exists': False} if the product does not exist.
        """
        stock_info = self.stocks.get(product_id)
        price_info = self.prices.get(product_id)

        if not stock_info or not price_info:
            return {"exists": False}

        stock = stock_info.get("stock_quantity", 0)
        base_price = price_info.get("base_price", 0.0)
        cost_price = price_info.get("cost_price", 0.0)

        discounted_price = base_price * (1 - (requested_discount / 100))
        profit = discounted_price - cost_price
        margin_percentage = (profit / discounted_price) * 100 if discounted_price > 0 else 0.0

        return {
            "exists": True,
            "stock_quantity": stock,
            "margin_percentage": round(margin_percentage, 2)
        }
