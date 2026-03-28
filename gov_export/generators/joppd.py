"""JOPPD Generator — adapter za postojeći payroll/joppd_generator.py"""

class JOPPDGenerator:
    def generate(self, export):
        from payroll.joppd_generator import generate_joppd_xml
        from payroll.models import PayrollRun, Payslip
        
        run = PayrollRun.objects.filter(
            company=export.company,
            year=export.period_start.year,
            month=export.period_start.month,
        ).first()
        
        if not run:
            raise ValueError(f'Nema PayrollRun za {export.period_start}')
        
        payslips = Payslip.objects.filter(payroll_run=run)
        return generate_joppd_xml(export.company, run, payslips)
