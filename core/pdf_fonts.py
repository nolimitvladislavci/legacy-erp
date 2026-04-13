import logging

logger = logging.getLogger(__name__)
"""
Register DejaVu Sans fonts for xhtml2pdf PDF generation.

DejaVu Sans supports full Latin Extended character set including
Croatian characters (č, ć, š, ž, đ) which are missing from
the default Helvetica/Arial fonts used by xhtml2pdf.

Call register_pdf_fonts() once at Django startup (AppConfig.ready)
to ensure all PDF generators use DejaVu Sans.
"""

_registered = False


def register_pdf_fonts():
    """Register DejaVu Sans with reportlab and override xhtml2pdf font mapping."""
    global _registered
    if _registered:
        return

    import os

    font_dir = '/usr/share/fonts/truetype/dejavu'
    regular = os.path.join(font_dir, 'DejaVuSans.ttf')
    bold = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')

    if not os.path.exists(regular):
        import logging
        logging.getLogger(__name__).warning(
            'DejaVu Sans font not found at %s — Croatian PDF chars may be broken', regular
        )
        return

    # 1. Register fonts with reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    from reportlab.pdfbase.ttfonts import TTFont

    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', regular))
    except Exception:
        pass  # Already registered
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold))
    except Exception:
        logger.exception("Unexpected error in: pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', ")

    registerFontFamily(
        'DejaVuSans',
        normal='DejaVuSans',
        bold='DejaVuSans-Bold',
        italic='DejaVuSans',
        boldItalic='DejaVuSans-Bold',
    )

    # 2. Override xhtml2pdf's DEFAULT_FONT mapping so that any CSS
    #    font-family referencing Helvetica/Arial/sans-serif will
    #    resolve to DejaVuSans (which has č, ć, š, ž, đ glyphs).
    try:
        from xhtml2pdf.default import DEFAULT_FONT

        overrides = {
            'dejavu': 'DejaVuSans',
            'dejavusans': 'DejaVuSans',
            'dejavu sans': 'DejaVuSans',
            'helvetica': 'DejaVuSans',
            'helvetica-bold': 'DejaVuSans-Bold',
            'helvetica-boldoblique': 'DejaVuSans-Bold',
            'helvetica-oblique': 'DejaVuSans',
            'arial': 'DejaVuSans',
            'sans': 'DejaVuSans',
            'sansserif': 'DejaVuSans',
            'sans-serif': 'DejaVuSans',
            'verdana': 'DejaVuSans',
            'geneva': 'DejaVuSans',
        }
        DEFAULT_FONT.update(overrides)
    except ImportError:
        pass  # xhtml2pdf not installed

    _registered = True
