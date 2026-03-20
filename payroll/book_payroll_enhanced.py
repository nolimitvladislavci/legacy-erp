"""
Enhanced payroll journal entry booking with 8 Croatian standard accounts.

Konta:
  4200 - Bruto plaće (Gross salaries expense)
  4210 - Doprinosi na plaće - zdravstveno (Employer health contribution)
  2410 - Obveza za neto plaće (Net salary liability)
  2411 - Obveza za MIO I. stup (Pension pillar I liability)
  2412 - Obveza za MIO II. stup (Pension pillar II liability)
  2420 - Obveza za porez na dohodak (Income tax liability)
  2421 - Obveza za prirez (Surtax liability)
  2430 - Obveza za doprinose na plaće (Employer contribution liability)
"""
from decimal import Decimal, ROUND_HALF_UP


def book_payroll_to_ledger_hr(payroll_run, breakdowns, create_entry_fn):
    """
    Create a detailed JournalEntry from payroll run using Croatian 8-account standard.

    Args:
        payroll_run: PayrollRun instance (company, year, month)
        breakdowns: list of dicts from hr_calculator.izracunaj_placu(), each with:
            bruto, mio_1_stup, mio_2_stup, dohodak, osobni_odbitak, porezna_osnovica,
            porez, prirez, neto, doprinos_zdravstvo
        create_entry_fn: callable(company, date, opis, lines) that creates the
            JournalEntry + LedgerLines. Each line is a dict:
            {'konto': str, 'opis': str, 'duguje': Decimal, 'potrazuje': Decimal}

    Returns:
        The created JournalEntry instance.
    """
    from datetime import date
    import calendar

    last_day = calendar.monthrange(payroll_run.year, payroll_run.month)[1]
    entry_date = date(payroll_run.year, payroll_run.month, last_day)

    # Aggregate totals
    t_bruto = Decimal('0')
    t_mio1 = Decimal('0')
    t_mio2 = Decimal('0')
    t_porez = Decimal('0')
    t_prirez = Decimal('0')
    t_neto = Decimal('0')
    t_zdravstvo = Decimal('0')

    for bd in breakdowns:
        t_bruto += bd['bruto']
        t_mio1 += bd['mio_1_stup']
        t_mio2 += bd['mio_2_stup']
        t_porez += bd['porez']
        t_prirez += bd['prirez']
        t_neto += bd['neto']
        t_zdravstvo += bd['doprinos_zdravstvo']

    q = lambda x: x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    mjesec = f"{payroll_run.month:02d}/{payroll_run.year}"
    opis = f"Obračun plaća {mjesec}"

    lines = [
        # DUGOVNA strana (rashodi)
        {
            'konto': '4200',
            'opis': f'Bruto plaće {mjesec}',
            'duguje': q(t_bruto),
            'potrazuje': Decimal('0'),
        },
        {
            'konto': '4210',
            'opis': f'Doprinos zdravstvo {mjesec}',
            'duguje': q(t_zdravstvo),
            'potrazuje': Decimal('0'),
        },
        # POTRAŽNA strana (obveze)
        {
            'konto': '2410',
            'opis': f'Obveza neto plaće {mjesec}',
            'duguje': Decimal('0'),
            'potrazuje': q(t_neto),
        },
        {
            'konto': '2411',
            'opis': f'Obveza MIO I. stup {mjesec}',
            'duguje': Decimal('0'),
            'potrazuje': q(t_mio1),
        },
        {
            'konto': '2412',
            'opis': f'Obveza MIO II. stup {mjesec}',
            'duguje': Decimal('0'),
            'potrazuje': q(t_mio2),
        },
        {
            'konto': '2420',
            'opis': f'Obveza porez na dohodak {mjesec}',
            'duguje': Decimal('0'),
            'potrazuje': q(t_porez),
        },
        {
            'konto': '2421',
            'opis': f'Obveza prirez {mjesec}',
            'duguje': Decimal('0'),
            'potrazuje': q(t_prirez),
        },
        {
            'konto': '2430',
            'opis': f'Obveza doprinos zdravstvo {mjesec}',
            'duguje': Decimal('0'),
            'potrazuje': q(t_zdravstvo),
        },
    ]

    # Verify double-entry balance
    total_duguje = sum(l['duguje'] for l in lines)
    total_potrazuje = sum(l['potrazuje'] for l in lines)
    assert total_duguje == total_potrazuje, (
        f"Temeljnica nije uravnotežena: duguje={total_duguje}, potrazuje={total_potrazuje}"
    )

    # Filter out zero lines (e.g., MIO II when no 2nd pillar, prirez when 0%)
    lines = [l for l in lines if l['duguje'] > 0 or l['potrazuje'] > 0]

    return create_entry_fn(payroll_run.company, entry_date, opis, lines)
