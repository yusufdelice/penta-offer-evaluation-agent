import json
from pathlib import Path
from typing import Dict, Any, Optional

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "offers.json"


class CRMClient:
    """
    CRM İstemcisi.
    Teklif ve müşteri kayıtlarını 'data/offers.json' dosyasından okuyarak
    in-memory hafızasında tutar.
    """

    def __init__(self, data_path: Path = DATA_FILE):
        self.data_path = Path(data_path)
        self.offers: Dict[str, Dict[str, Any]] = {}
        self.load_data()

    def load_data(self) -> None:
        """offers.json dosyasını yükler ve offer_id anahtarıyla indeksler."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"CRM veri dosyası bulunamadı: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            offers_list = json.load(f)

        self.offers = {item["offer_id"]: item for item in offers_list}

    def get_offer(self, offer_id: str) -> Optional[Dict[str, Any]]:
        """Verilen offer_id'ye ait teklifi döner, kayıt yoksa None döner."""
        return self.offers.get(offer_id)