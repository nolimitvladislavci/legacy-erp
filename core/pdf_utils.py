# core/pdf_utils.py
# Centralni registar za PDF predloške i pomoćne funkcije.

from django.conf import settings
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class PDFTemplateRegistry:
    """
    Centralni registar za PDF predloške.
    Omogućuje registraciju, dohvaćanje i provjeru postojanja predložaka
    za različite tipove dokumenata i tvrtke.
    """
    def __init__(self):
        # Koristimo defaultdict za lakše rukovanje nepostojećim ključevima
        # Struktura: {company_id: {template_name: template_path}}
        self._registry = defaultdict(dict)

    def register_template(self, company_id, template_name, template_path):
        """
        Registrira PDF predložak za određenu tvrtku i naziv predloška.
        
        Args:
            company_id (int): ID tvrtke za koju se registrira predložak.
            template_name (str): Naziv predloška (npr. 'invoice_template', 'delivery_note_template').
            template_path (str): Puna staza do PDF predloška (relativno ili apsolutno).
        """
        if not isinstance(company_id, int):
            try:
                company_id = int(company_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid company_id type: {type(company_id)}. Must be an integer.")
                raise TypeError("company_id must be an integer")

        if not isinstance(template_name, str) or not template_name:
            logger.error(f"Invalid template_name: '{template_name}'. Must be a non-empty string.")
            raise ValueError("template_name must be a non-empty string")

        if not isinstance(template_path, str) or not template_path:
            logger.error(f"Invalid template_path: '{template_path}'. Must be a non-empty string.")
            raise ValueError("template_path must be a non-empty string")

        self._registry[company_id][template_name] = template_path
        logger.info(f"Registered template '{template_name}' for company ID {company_id} at '{template_path}'.")

    def get_template(self, company_id, template_name):
        """
        Dohvaća stazu do PDF predloška za danu tvrtku i naziv predloška.
        Ako predložak nije pronađen, vraća None.
        
        Args:
            company_id (int): ID tvrtke.
            template_name (str): Naziv predloška.
            
        Returns:
            str or None: Staza do predloška ili None ako predložak ne postoji.
        """
        if not isinstance(company_id, int):
            try:
                company_id = int(company_id)
            except (ValueError, TypeError):
                logger.warning(f"Attempted to get template with invalid company_id type: {type(company_id)}. Returning None.")
                return None

        template_path = self._registry.get(company_id, {}).get(template_name)
        if template_path:
            logger.debug(f"Retrieved template '{template_name}' for company ID {company_id}: '{template_path}'.")
        else:
            logger.debug(f"Template '{template_name}' not found for company ID {company_id}.")
        return template_path

    def has_template(self, company_id, template_name):
        """
        Provjerava postoji li registrirani predložak za danu tvrtku i naziv.
        
        Args:
            company_id (int): ID tvrtke.
            template_name (str): Naziv predloška.
            
        Returns:
            bool: True ako predložak postoji, False inače.
        """
        if not isinstance(company_id, int):
            try:
                company_id = int(company_id)
            except (ValueError, TypeError):
                return False
        
        return template_name in self._registry.get(company_id, {})

    def clear_registry(self):
        """
        Briše sve registrirane predloške iz registra.
        Koristiti oprezno, uglavnom za testiranje.
        """
        self._registry.clear()
        logger.info("PDF template registry cleared.")

# Inicijalizacija globalnog registra
# Ovo osigurava da imamo samo jednu instancu registra u cijeloj aplikaciji.
PDF_TEMPLATE_REGISTRY = PDFTemplateRegistry()


# Primjeri korištenja (mogu se ukloniti u produkciji ili premjestiti u tests/)
# if settings.DEBUG:
#     # Pretpostavimo da imamo Company model s ID-jevima 1, 2, 3
#     # I da imamo template fajlove na nekim stazama
#     company1_id = 1
#     company2_id = 2

#     # Registracija predložaka za tvrtku 1
#     PDF_TEMPLATE_REGISTRY.register_template(
#         company1_id, 'invoice_template', '/app/templates/pdf/company1_invoice.html'
#     )
#     PDF_TEMPLATE_REGISTRY.register_template(
#         company1_id, 'delivery_note_template', '/app/templates/pdf/company1_delivery_note.html'
#     )

#     # Registracija predložaka za tvrtku 2
#     PDF_TEMPLATE_REGISTRY.register_template(
#         company2_id, 'invoice_template', '/app/templates/pdf/company2_invoice.html'
#     )

#     # Dohvaćanje predložaka
#     template = PDF_TEMPLATE_REGISTRY.get_template(company1_id, 'invoice_template')
#     print(f"Company 1 Invoice Template: {template}")

#     template = PDF_TEMPLATE_REGISTRY.get_template(company2_id, 'invoice_template')
#     print(f"Company 2 Invoice Template: {template}")

#     template = PDF_TEMPLATE_REGISTRY.get_template(company1_id, 'non_existent_template')
#     print(f"Non-existent template for Company 1: {template}")

#     # Provjera postojanja
#     print(f"Has invoice template for Company 1: {PDF_TEMPLATE_REGISTRY.has_template(company1_id, 'invoice_template')}")
#     print(f"Has non_existent_template for Company 1: {PDF_TEMPLATE_REGISTRY.has_template(company1_id, 'non_existent_template')}")