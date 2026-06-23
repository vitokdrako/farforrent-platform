"""
Розумний пошук товарів:
- Багатопольний (name, sku, color, material, description, hashtags, components, categories)
- Tolerantний до опечаток (rapidfuzz)
- Семантичний для розмірів (маленький/середній/великий)

Використання:
    from utils.smart_search import parse_query, score_product
    parsed = parse_query("велика зелена ваза")
    score = score_product(product_dict, parsed)
"""
import re
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


# Стопорні слова — не вживаються в пошуку
STOP_WORDS = {"і", "та", "на", "в", "у", "з", "до", "для", "от", "у", "в", "the", "a", "an", "and", "or", "of", "for"}

# Розмірні префікси (нормалізовані)
SIZE_KEYWORDS = {
    "small":  ["маленьк", "маленьк", "мал", "невеличк", "невеликий", "крихітн", "малесеньк", "малий", "мала", "мале"],
    "medium": ["середн", "середн", "середній", "середня", "середнє"],
    "large":  ["велик", "великий", "велика", "велике", "височезн", "височенн", "велетенс", "велик"],
}

# Діапазони висоти/діаметра в см
SIZE_RANGES = {
    "small":  (0, 15.0),
    "medium": (15.01, 40.0),
    "large":  (40.01, 9999.0),
}


@dataclass
class ParsedQuery:
    raw: str
    tokens: List[str]            # звичайні слова, нормалізовані
    size_filter: Optional[str]    # 'small'/'medium'/'large' або None


def _normalize(text: str) -> str:
    """Нижній регістр + прибрати зайві символи."""
    if not text:
        return ""
    t = text.lower().strip()
    # Залишити літери (укр+анг), цифри і пробіли
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _detect_size(word: str) -> Optional[str]:
    """Повертає 'small'/'medium'/'large' якщо слово збігається з розмірним префіксом."""
    for size, prefixes in SIZE_KEYWORDS.items():
        if any(word.startswith(p) for p in prefixes):
            return size
    return None


def parse_query(query: str) -> ParsedQuery:
    """Розбити запит на токени + виокремити розмірний фільтр."""
    norm = _normalize(query or "")
    tokens: List[str] = []
    size_filter: Optional[str] = None

    for word in norm.split():
        if word in STOP_WORDS:
            continue
        # Зловити розмір
        size = _detect_size(word)
        if size and not size_filter:
            size_filter = size
            continue  # розмірне слово не йде в звичайні токени
        if len(word) >= 2:
            tokens.append(word)

    return ParsedQuery(raw=query, tokens=tokens, size_filter=size_filter)


def _searchable_fields(product: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """
    Розділяємо поля на:
    - strong: ключові короткі поля (name, color, material, category тощо)
    - weak: довгі описи (description, components, hashtags) — пошук як substring
    """
    strong = []
    for key in ("name", "sku", "color", "material",
                "category_name", "subcategory_name", "size", "shape"):
        v = product.get(key)
        if v:
            strong.append(_normalize(str(v)))

    weak = []
    for key in ("description", "components"):
        v = product.get(key)
        if v:
            weak.append(_normalize(str(v)))

    h = product.get("hashtags")
    if h:
        if isinstance(h, str):
            try:
                h = json.loads(h)
            except Exception:
                pass
        if isinstance(h, (list, tuple)):
            for x in h:
                weak.append(_normalize(str(x)))
        elif isinstance(h, dict):
            for v in h.values():
                weak.append(_normalize(str(v)))

    return strong, weak


def _build_searchable_text(product: Dict[str, Any]) -> str:
    """Збірка тексту з усіх пошукових полів товару (для backward compat)."""
    strong, weak = _searchable_fields(product)
    return " ".join(strong + weak).strip()


def _size_value(product: Dict[str, Any]) -> Optional[float]:
    """Спробувати визначити "розмір" товару (висота, інакше діаметр)."""
    for key in ("height_cm", "diameter_cm", "width_cm"):
        v = product.get(key)
        if v is not None:
            try:
                f = float(v)
                if f > 0:
                    return f
            except (TypeError, ValueError):
                pass
    # Fallback: спробувати парсити з name або size ("Ваза 26 см")
    text = f"{product.get('name', '')} {product.get('size', '')}"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*см", text, flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


def _matches_size(product: Dict[str, Any], size_filter: str) -> bool:
    """Чи підходить товар під розмірний фільтр."""
    if not size_filter:
        return True
    val = _size_value(product)
    if val is None:
        return False  # без розміру — не показуємо при явному фільтрі
    lo, hi = SIZE_RANGES[size_filter]
    return lo <= val <= hi


def score_product(product: Dict[str, Any], parsed: ParsedQuery) -> float:
    """
    Скор товару під запит. 0 = не підходить, 100 = ідеально.
    Беремо WRatio per token per field, AND-логіку (min) між токенами.
    """
    # 1. Розмірний фільтр — жорсткий
    if parsed.size_filter and not _matches_size(product, parsed.size_filter):
        return 0.0

    # 2. Якщо немає звичайних токенів — все що пройшло розмір, проходить
    if not parsed.tokens:
        return 100.0 if parsed.size_filter else 50.0

    strong, weak = _searchable_fields(product)
    if not strong and not weak:
        return 0.0

    # 3. Скоринг по кожному токену
    if not RAPIDFUZZ_AVAILABLE:
        # Fallback: проста підрядкова перевірка
        all_text = " ".join(strong + weak)
        hits = sum(1 for t in parsed.tokens if t in all_text)
        return (hits / len(parsed.tokens)) * 100.0

    token_scores = []
    for token in parsed.tokens:
        # Strong поля — fuzz.WRatio (weighted ratio, працює добре і для коротких і довгих)
        best_strong = max(
            (fuzz.WRatio(token, f) for f in strong),
            default=0,
        ) if strong else 0
        # Weak поля — substring або token_set_ratio (для довгих описів)
        in_weak_substring = any(token in f for f in weak)
        if in_weak_substring:
            best_weak = 95  # підстрока в описі — майже як точне
        elif weak:
            best_weak = max((fuzz.partial_ratio(token, f) for f in weak), default=0)
        else:
            best_weak = 0
        token_scores.append(max(best_strong, best_weak))

    # AND-логіка: усі слова мають знайтись
    min_score = min(token_scores)
    avg_score = sum(token_scores) / len(token_scores)
    # Більш зважений на мінімум — слабке слово знижує загальний скор
    return 0.6 * min_score + 0.4 * avg_score


def filter_and_rank(
    products: List[Dict[str, Any]],
    query: str,
    threshold: float = 65.0,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Відфільтрувати та посортувати товари за релевантністю.

    Args:
        products: список товарів (dict)
        query: пошуковий запит
        threshold: мінімальний скор (0-100)
        limit: обмежити кількість результатів

    Returns:
        Відфільтровані товари посортовані за спаданням релевантності.
    """
    if not query or not query.strip():
        return products[:limit] if limit else products

    parsed = parse_query(query)

    # Якщо запит зовсім порожній після парсингу — повертаємо все
    if not parsed.tokens and not parsed.size_filter:
        return products[:limit] if limit else products

    scored = []
    for p in products:
        s = score_product(p, parsed)
        if s >= threshold:
            scored.append((s, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    result = [p for _, p in scored]
    return result[:limit] if limit else result
