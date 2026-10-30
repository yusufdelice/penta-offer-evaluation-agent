import re
from typing import Optional


def mask_email(email: Optional[str]) -> str:
    """
    Masks an email address (e.g., 'buyer@enterprisetech.com' -> 'b***@e*************h.com').
    Corporate domain names may contain commercial identities, so the domain is masked as well.
    """
    if not email or "@" not in email:
        return "***"

    local_part, domain = email.split("@", 1)

    if len(local_part) <= 1:
        masked_local = "*"
    else:
        masked_local = f"{local_part[0]}***"

    dot_index = domain.rfind(".")
    if dot_index > 0:
        domain_name = domain[:dot_index]
        tld = domain[dot_index:]

        if len(domain_name) <= 2:
            masked_domain_name = "*" * len(domain_name)
        else:
            masked_domain_name = f"{domain_name[0]}{'*' * (len(domain_name) - 2)}{domain_name[-1]}"

        masked_domain = f"{masked_domain_name}{tld}"
    else:
        if len(domain) <= 2:
            masked_domain = "*" * len(domain)
        else:
            masked_domain = f"{domain[0]}{'*' * (len(domain) - 2)}{domain[-1]}"

    return f"{masked_local}@{masked_domain}"


def mask_name(name: Optional[str]) -> str:
    """
    Masks full personal or partner names (e.g., 'Acme Technology' -> 'A*** T*********').
    """
    if not name:
        return "*"

    words = name.split()
    masked_words = []

    for word in words:
        if len(word) <= 1:
            masked_words.append("*")
        else:
            masked_words.append(word[0] + "*" * (len(word) - 1))

    return " ".join(masked_words)


def mask_phone(phone: Optional[str]) -> str:
    """
    Masks phone numbers keeping only the last 4 digits (e.g., '+15551234567' -> '+*******4567').
    """
    if not phone:
        return "****"

    digits_only = re.sub(r'\D', '', phone)

    if len(digits_only) <= 4:
        return "****"

    visible_end = digits_only[-4:]
    masked_start = "*" * (len(digits_only) - 4)

    if phone.startswith("+"):
        return f"+{masked_start}{visible_end}"

    return f"{masked_start}{visible_end}"


def mask_offer_data(offer_data: dict) -> dict:
    """
    Returns a copy of the offer payload with all customer PII scrubbed/masked.
    Does not mutate the original data dictionary.
    """
    masked = offer_data.copy()

    if "customer" in masked and isinstance(masked["customer"], dict):
        masked["customer"] = masked["customer"].copy()

        if "email" in masked["customer"] and masked["customer"]["email"] is not None:
            masked["customer"]["email"] = mask_email(masked["customer"]["email"])

        if "name" in masked["customer"] and masked["customer"]["name"] is not None:
            masked["customer"]["name"] = mask_name(masked["customer"]["name"])

        if "phone" in masked["customer"] and masked["customer"]["phone"] is not None:
            masked["customer"]["phone"] = mask_phone(masked["customer"]["phone"])

    return masked
