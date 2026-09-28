import json
from pathlib import Path
from typing import Dict, Any

STOCK_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "stock.json"
PRICES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "prices.json"


class ERPClient:
    """
    ERP İstemcisi.
    Stok ve fiyat verilerini 'data/stock.json' ve 'data/prices.json' dosyalarından
    okuyarak in-memory hafızasında tutar ve marj hesaplaması yapar.
    """

    def __init__(self, stock_path: Path = STOCK_FILE, prices_path: Path = PRICES_FILE):
        self.stock_path = Path(stock_path)
        self.prices_path = Path(prices_path)
        self.stocks: Dict[str, Dict[str, Any]] = {}
        self.prices: Dict[str, Dict[str, Any]] = {}
        self.load_data()

    def load_data(self) -> None:
        """stock.json ve prices.json dosyalarını yükler."""
        if not self.stock_path.exists():
            raise FileNotFoundError(f"ERP stok veri dosyası bulunamadı: {self.stock_path}")

        if not self.prices_path.exists():
            raise FileNotFoundError(f"ERP fiyat veri dosyası bulunamadı: {self.prices_path}")

        with open(self.stock_path, "r", encoding="utf-8") as f:
            self.stocks = json.load(f)

        with open(self.prices_path, "r", encoding="utf-8") as f:
            self.prices = json.load(f)

    def get_product_data(self, product_id: str, requested_discount: float = 0.0) -> Dict[str, Any]:
        """
        Ürünün stok miktarını ve talep edilen indirime göre kar marjını döner.
        Ürün bulunamazsa {'exists': False} döner.
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
