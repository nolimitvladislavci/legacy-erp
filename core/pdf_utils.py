import logging

logger = logging.getLogger(__name__)

PDF_TEMPLATE_REGISTRY = {}


def register_pdf_template(name, path):
    """
    Registers a PDF template with a given name and its file path.
    """
    if name in PDF_TEMPLATE_REGISTRY:
        logger.warning(
            f"PDF template '{name}' is being re-registered. Old path: {PDF_TEMPLATE_REGISTRY[name]}, New path: {path}"
        )
    PDF_TEMPLATE_REGISTRY[name] = path
    logger.info(f"Registered PDF template '{name}' at '{path}'")


def get_pdf_template_path(name):
    """
    Retrieves the file path for a registered PDF template.
    """
    path = PDF_TEMPLATE_REGISTRY.get(name)
    if not path:
        logger.error(f"PDF template '{name}' not found in registry.")
    return path
