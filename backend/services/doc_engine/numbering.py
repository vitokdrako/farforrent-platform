"""
Document Numbering - генерація номерів документів
Формат: {SERIES}-{YEAR}-{SEQ:06d}
Приклад: INV-2025-000123
"""
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

def generate_doc_number(db: Session, series: str) -> str:
    """
    Генерує унікальний номер документа.
    Використовує таблицю doc_number_sequences для атомарної генерації.
    MySQL compatible version.
    """
    year = datetime.now().year
    
    # Спочатку перевіряємо чи існує запис
    result = db.execute(text("""
        SELECT current_seq FROM doc_number_sequences 
        WHERE series = :series AND year = :year
        FOR UPDATE
    """), {"series": series, "year": year})
    
    row = result.fetchone()
    
    if row:
        # Оновлюємо існуючий запис
        new_seq = row[0] + 1
        db.execute(text("""
            UPDATE doc_number_sequences 
            SET current_seq = :new_seq, updated_at = NOW()
            WHERE series = :series AND year = :year
        """), {"new_seq": new_seq, "series": series, "year": year})
        seq = new_seq
    else:
        # Створюємо новий запис (MySQL syntax with ON DUPLICATE KEY)
        db.execute(text("""
            INSERT INTO doc_number_sequences (series, year, current_seq, created_at, updated_at)
            VALUES (:series, :year, 1, NOW(), NOW())
            ON DUPLICATE KEY UPDATE current_seq = current_seq + 1
        """), {"series": series, "year": year})
        seq = 1
    
    db.commit()
    
    return f"{series}-{year}-{seq:06d}"

def parse_doc_number(doc_number: str) -> dict:
    """Розбирає номер документа на компоненти"""
    parts = doc_number.split("-")
    if len(parts) != 3:
        return None
    return {
        "series": parts[0],
        "year": int(parts[1]),
        "seq": int(parts[2])
    }
