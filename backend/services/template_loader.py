"""
DB-override Jinja2 Loader.
Перевіряє document_templates таблицю перед файловою системою.
"""
from jinja2 import BaseLoader, TemplateNotFound
from sqlalchemy import text


class DBOverrideLoader(BaseLoader):
    """Jinja2 loader: DB override → FileSystem fallback."""

    def __init__(self, file_loader):
        self.file_loader = file_loader

    def get_source(self, environment, template):
        doc_type = self._extract_doc_type(template)
        if doc_type:
            try:
                from database_rentalhub import get_rh_db_sync
                db = get_rh_db_sync()
                try:
                    row = db.execute(text(
                        "SELECT template_content FROM document_templates WHERE doc_type = :dt"
                    ), {"dt": doc_type}).fetchone()
                    if row and row[0]:
                        return row[0], f"db:{doc_type}", lambda: False
                finally:
                    db.close()
            except Exception:
                pass
        return self.file_loader.get_source(environment, template)

    @staticmethod
    def _extract_doc_type(template):
        name = template.replace("documents/", "").replace("\\", "/")
        # "legal/master_agreement.html" -> "master_agreement"
        # "quote/v1.html" -> "quote"
        # "contract_rent/v1.html" -> "contract_rent"
        if "/" in name:
            parts = name.split("/")
            # If first part is a known directory prefix, use the second part
            if parts[0] in ("legal",) and len(parts) > 1:
                name = parts[1]
            else:
                name = parts[0]
        # "quote.html" -> "quote"
        if name.endswith(".html"):
            name = name[:-5]
        # Skip base/partial templates
        if name.startswith("_") or name == "":
            return None
        return name
