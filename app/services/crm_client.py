import json
from pathlib import Path
from typing import Dict, Any, Optional

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "offers.json"


class CRMClient:
    """
    CRM Client adapter.
    Reads offer and customer master records from 'data/offers.json'
    and indexes them in memory.
    """

    def __init__(self, data_path: Path = DATA_FILE):
        self.data_path = Path(data_path)
        self.offers: Dict[str, Dict[str, Any]] = {}
        self.load_data()

    def load_data(self) -> None:
        """Loads offers.json and indexes records by offer_id."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"CRM data file not found: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            offers_list = json.load(f)

        self.offers = {item["offer_id"]: item for item in offers_list}

    def get_offer(self, offer_id: str) -> Optional[Dict[str, Any]]:
        """Returns the offer associated with the given offer_id, or None if not found."""
        return self.offers.get(offer_id)
