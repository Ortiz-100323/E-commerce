import re
import unicodedata

from ecommerce.catalog.domain.importing.policies import SkuIdentityPolicy

WORD = re.compile(r"[^\W_]+")


def normalize_name(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def trigrams(text: str) -> set[str]:
    found: set[str] = set()
    for word in WORD.findall(normalize_name(text)):
        padded = f"  {word} "
        found.update(padded[index : index + 3] for index in range(len(padded) - 2))
    return found


def similarity(left: str, right: str) -> float:
    first = trigrams(left)
    second = trigrams(right)
    union = first | second
    if not union:
        return 0.0
    return len(first & second) / len(union)


def same_product(
    catalog_name: str, row_name: str, policy: SkuIdentityPolicy, threshold: float
) -> bool:
    if policy is SkuIdentityPolicy.SKU_ONLY:
        return True
    if normalize_name(catalog_name) == normalize_name(row_name):
        return True
    if policy is SkuIdentityPolicy.EXACT_NAME:
        return False
    return similarity(catalog_name, row_name) >= threshold
