"""Document Engine for RentalHub"""
from .registry import DOC_REGISTRY, get_doc_config
from .data_builders import build_document_data
from .render import render_html, render_pdf
from .numbering import generate_doc_number
