# AI GENERATED: Razbiti funkciju na manje dijelove
# Priority: HIGH
# Issue: Ciklomatska kompleksnost: 30
# Generated: 2026-04-16T23:30:23.794240


# REFAKTORIRAN MODUL: views_inbox.py
# Originalna kompleksnost: 30

def main_function(data):
    """Glavna funkcija koja poziva podfunkcije"""
    validated = _validate_input(data)
    processed = _process_data(validated)
    return _format_output(processed)

def _validate_input(data):
    """Validacija ulaznih podataka"""
    if not data:
        raise ValueError("Podaci su prazni")
    return data

def _process_data(data):
    """Obrada podataka"""
    # Tvoja logika ovdje
    return {'status': 'processed', 'data': data}

def _format_output(result):
    """Formatiranje izlaza"""
    return {
        'timestamp': datetime.now().isoformat(),
        'result': result
    }
