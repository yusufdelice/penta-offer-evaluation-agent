import logging
import json
from datetime import datetime, timezone
from typing import Optional


from pathlib import Path

def setup_logger(name: str = "offer_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Terminal / Konsol çıktısı
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Kalıcı dosya çıktısı (project/logs/audit.log)
    try:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "audit.log", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass

    return logger


logger = setup_logger()


def log_offer_evaluation(offer_data: dict, result: dict, request_id: str) -> None:
    """
    Değerlendirme sonucunu sıfır PII (kişisel veri içermeyen) prensibiyle denetim günlüğüne yazar.
    İşlem takibi request_id ve offer_id üzerinden yapılır.
    """
    audit_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "offer_id": offer_data.get("offer_id", "UNKNOWN"),
        "product_id": offer_data.get("product_id"),
        "decision": result.get("decision"),
        "reason_codes": result.get("reason_codes"),
        "details": result.get("details")
    }

    logger.info(f"OFFER_EVALUATED | {json.dumps(audit_record, ensure_ascii=False)}")


def log_error(offer_id: str, error_message: str, request_id: Optional[str] = None) -> None:
    """
    Hata kayıtlarını işlem kimliğiyle denetim günlüğüne yazar.
    """
    error_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id or "N/A",
        "offer_id": offer_id,
        "error": error_message
    }

    logger.error(f"OFFER_ERROR | {json.dumps(error_record, ensure_ascii=False)}")
