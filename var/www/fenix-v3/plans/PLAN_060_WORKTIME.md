# PLAN_060 — Worktime & Attendance (Evidencija Radnog Vremena)

## Cilj
HR obveza: svaki poslodavac mora voditi evidenciju radnog vremena (Zakon o radu, čl. 7). Jednostavna web aplikacija za price in/out, pregledna tabela po tjednu/mjesecu, PDF za inspekciju rada.

## HR Zakonski okvir
- ZOR čl. 7: evidencija sati, prekovremeni max 8h/tjedan + 180h/godišnje
- Dnevni odmor: min 12h između smjena
- Tjedni odmor: min 24h neprekidno (nedjeljom)
- Evidencija čuvati: 6 godina
- Inspekcija rada može tražiti uvid u evidenciju

## Model
```python
class WorkSchedule(TenantModel):
    """Radno vrijeme za kompaniju/radnika."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # "Puno radno vrijeme", "Smjena A"
    hours_per_week = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("40.0"))
    monday_hours = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("8.0"))
    tuesday_hours = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("8.0"))
    wednesday_hours = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("8.0"))
    thursday_hours = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("8.0"))
    friday_hours = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("8.0"))
    saturday_hours = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("0.0"))
    sunday_hours = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("0.0"))


class TimeLog(TenantModel):
    """
    Jedna stavka evidencije. Clock-in ili clock-out.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="time_logs")
    employee = models.ForeignKey(
        "employee.Employee", on_delete=models.CASCADE, related_name="time_logs"
    )

    class LogType(models.TextChoices):
        WORK = "work", "Radno vrijeme"
        OVERTIME = "overtime", "Prekovremeni rad"
        SICK = "sick", "Bolovanje"
        VACATION = "vacation", "Godišnji odmor"
        PUBLIC_HOLIDAY = "public_holiday", "Državni praznik"
        OTHER_ABSENCE = "other", "Ostali izostanak"

    log_date = models.DateField()
    log_type = models.CharField(max_length=20, choices=LogType.choices, default=LogType.WORK)
    
    # Dolazak / Odlazak
    clock_in = models.TimeField(null=True)
    clock_out = models.TimeField(null=True)
    
    # Pauza (odmak)
    break_minutes = models.IntegerField(default=0)
    
    # Auto-izračun pri save()
    work_minutes = models.IntegerField(default=0)  # clock_out - clock_in - break
    overtime_minutes = models.IntegerField(default=0)
    
    note = models.CharField(max_length=200, blank=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        unique_together = [("company", "employee", "log_date")]
        indexes = [
            models.Index(fields=["company", "log_date"]),
            models.Index(fields=["employee", "log_date"]),
        ]

    def save(self, *args, **kwargs):
        if self.clock_in and self.clock_out:
            from datetime import datetime, timedelta
            dt_in = datetime.combine(self.log_date, self.clock_in)
            dt_out = datetime.combine(self.log_date, self.clock_out)
            if dt_out < dt_in:
                dt_out += timedelta(days=1)  # noćna smjena
            total_minutes = int((dt_out - dt_in).total_seconds() / 60)
            self.work_minutes = max(0, total_minutes - self.break_minutes)
            
            # Prekovremeni = sve iznad 8h dnevno
            standard = 8 * 60
            self.overtime_minutes = max(0, self.work_minutes - standard)
        super().save(*args, **kwargs)

    @property
    def work_hours_display(self) -> str:
        h = self.work_minutes // 60
        m = self.work_minutes % 60
        return f"{h}h {m:02d}m"
```

## URL struktura
```
/hr/worktime/                        → WorktimeListView (tjedni prikaz)
/hr/worktime/unos/                   → TimeLogCreateView
/hr/worktime/<uuid>/edit/            → TimeLogEditView
/hr/worktime/tjedan/<year>/<week>/   → WeeklyReportView
/hr/worktime/mjesec/<year>/<month>/  → MonthlyReportView
/hr/worktime/pdf/<year>/<month>/     → WorktimePDFView
/hr/worktime/api/clock-in/           → ClockInView (POST, HTMX)
/hr/worktime/api/clock-out/          → ClockOutView (POST, HTMX)
```

## Clock In/Out API (za terminal/tablet u firmi)
```python
class ClockInView(TenantView):
    permission_required = Permission.MANAGE_EMPLOYEES

    def post(self, request):
        employee_id = request.POST.get("employee_id")
        employee = get_object_or_404(Employee, id=employee_id, company=request.company)
        
        today = date.today()
        log, created = TimeLog.objects.get_or_create(
            company=request.company,
            employee=employee,
            log_date=today,
            defaults={"log_type": TimeLog.LogType.WORK}
        )
        
        if not created and log.clock_in:
            return JsonResponse({"ok": False, "error": "Već ste prijavljeni danas."})
        
        log.clock_in = timezone.localtime().time()
        log.save()
        
        return JsonResponse({
            "ok": True,
            "message": f"Dolazak zabilježen: {log.clock_in.strftime('%H:%M')}",
            "employee": employee.full_name,
        })


class ClockOutView(TenantView):
    permission_required = Permission.MANAGE_EMPLOYEES

    def post(self, request):
        employee_id = request.POST.get("employee_id")
        employee = get_object_or_404(Employee, id=employee_id, company=request.company)
        
        today = date.today()
        try:
            log = TimeLog.objects.get(company=request.company, employee=employee, log_date=today)
        except TimeLog.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Nema zabilježenog dolaska danas."})
        
        if not log.clock_in:
            return JsonResponse({"ok": False, "error": "Dolazak nije zabilježen."})
        if log.clock_out:
            return JsonResponse({"ok": False, "error": "Odlazak je već zabilježen."})
        
        log.clock_out = timezone.localtime().time()
        log.save()  # auto-izračun work_minutes
        
        return JsonResponse({
            "ok": True,
            "message": f"Odlazak: {log.clock_out.strftime('%H:%M')} | Odrađeno: {log.work_hours_display}",
            "work_minutes": log.work_minutes,
        })
```

## MonthlyReportView
```python
class MonthlyReportView(TenantView):
    permission_required = Permission.VIEW_EMPLOYEES
    template_name = "worktime/monthly.html"

    def get(self, request, year, month):
        employees = Employee.objects.filter(
            company=request.company,
            employment_start__lte=date(year, month, 1),
        ).filter(
            models.Q(employment_end__isnull=True) | models.Q(employment_end__gte=date(year, month, 1))
        )
        
        logs = TimeLog.objects.filter(
            company=request.company,
            log_date__year=year,
            log_date__month=month,
        ).select_related("employee").order_by("employee__last_name", "log_date")
        
        # Grupiraj po radniku
        from itertools import groupby
        from operator import attrgetter
        employee_data = []
        for emp in employees:
            emp_logs = [l for l in logs if l.employee_id == emp.id]
            total_work = sum(l.work_minutes for l in emp_logs)
            total_overtime = sum(l.overtime_minutes for l in emp_logs)
            working_days = sum(1 for l in emp_logs if l.log_type == TimeLog.LogType.WORK and l.work_minutes > 0)
            vacation_days = sum(1 for l in emp_logs if l.log_type == TimeLog.LogType.VACATION)
            sick_days = sum(1 for l in emp_logs if l.log_type == TimeLog.LogType.SICK)
            employee_data.append({
                "employee": emp,
                "logs": emp_logs,
                "total_work_hours": total_work // 60,
                "total_overtime_hours": total_overtime // 60,
                "working_days": working_days,
                "vacation_days": vacation_days,
                "sick_days": sick_days,
            })
        
        return render(request, self.template_name, {
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "employee_data": employee_data,
            "calendar_days": list(self._month_days(year, month)),
        })

    def _month_days(self, year: int, month: int):
        import calendar
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            yield date(year, month, day)
```

## Template: worktime/monthly.html
Tabela s radnicima po redcima, datumima po stupcima:

```html
<div class="overflow-x-auto">
  <table class="table text-sm">
    <thead>
      <tr>
        <th class="sticky left-0 bg-white">Radnik</th>
        {% for day in calendar_days %}
        <th class="w-8 text-center {% if day.weekday >= 5 %}bg-gray-50{% endif %}">
          <div class="text-xs text-gray-400">{{ day|date:"D" }}</div>
          <div>{{ day.day }}</div>
        </th>
        {% endfor %}
        <th>Sati</th><th>Prekov.</th><th>GO</th><th>Bol.</th>
      </tr>
    </thead>
    <tbody>
      {% for item in employee_data %}
      <tr>
        <td class="sticky left-0 bg-white font-medium">{{ item.employee.full_name }}</td>
        {% for day in calendar_days %}
        <td class="text-center text-xs {% if day.weekday >= 5 %}bg-gray-50{% endif %}">
          {% with log=item.logs|get_log_for_day:day %}
            {% if log %}
              {% if log.log_type == "vacation" %}
                <span class="text-blue-500" title="Godišnji">GO</span>
              {% elif log.log_type == "sick" %}
                <span class="text-red-500" title="Bolovanje">B</span>
              {% elif log.work_minutes > 0 %}
                <span class="text-green-600" title="{{ log.clock_in }}-{{ log.clock_out }}">
                  {{ log.work_minutes|divide:60|floatformat:1 }}h
                </span>
              {% endif %}
            {% elif day.weekday < 5 %}
              <span class="text-gray-200">—</span>
            {% endif %}
          {% endwith %}
        </td>
        {% endfor %}
        <td class="text-right font-mono">{{ item.total_work_hours }}h</td>
        <td class="text-right font-mono {% if item.total_overtime_hours > 0 %}text-orange-600{% endif %}">
          {{ item.total_overtime_hours }}h
        </td>
        <td class="text-center">{{ item.vacation_days }}</td>
        <td class="text-center">{{ item.sick_days }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

## PDF (WeasyPrint)
A4 landscape, za inspekciju rada. `WorktimePDFView` — identičan layout kao HTML tabela, sa zaglavljem firme i potpisom.

## Violations check
```python
def check_worktime_violations(company, year: int, month: int) -> list[str]:
    """
    Provjeri zakonske kršenja:
    - Prekovremeni > 8h/tjedan
    - Odmor između smjena < 12h
    """
    violations = []
    logs = TimeLog.objects.filter(
        company=company,
        log_date__year=year,
        log_date__month=month,
    ).select_related("employee").order_by("employee", "log_date")
    
    from itertools import groupby
    for employee, emp_logs in groupby(logs, key=lambda l: l.employee):
        emp_logs = list(emp_logs)
        
        # Provjeri tjedni prekovremeni
        from collections import defaultdict
        weekly_overtime = defaultdict(int)
        for log in emp_logs:
            week = log.log_date.isocalendar()[1]
            weekly_overtime[week] += log.overtime_minutes
        
        for week, minutes in weekly_overtime.items():
            if minutes > 8 * 60:
                violations.append(
                    f"{employee.full_name}: tjedan {week} — {minutes//60}h prekovremenih (max 8h)"
                )
        
        # Provjeri odmor između smjena (12h)
        for i in range(len(emp_logs) - 1):
            if emp_logs[i].clock_out and emp_logs[i+1].clock_in:
                from datetime import datetime
                dt_out = datetime.combine(emp_logs[i].log_date, emp_logs[i].clock_out)
                dt_in = datetime.combine(emp_logs[i+1].log_date, emp_logs[i+1].clock_in)
                rest_hours = (dt_in - dt_out).total_seconds() / 3600
                if rest_hours < 12:
                    violations.append(
                        f"{employee.full_name}: {emp_logs[i].log_date} → {emp_logs[i+1].log_date} — odmor samo {rest_hours:.1f}h (min 12h)"
                    )
    
    return violations
```

## Testovi
```python
def test_work_minutes_calculated_on_save():
    log = TimeLogFactory(clock_in=time(8, 0), clock_out=time(16, 0), break_minutes=30)
    assert log.work_minutes == 450  # 7.5h

def test_overtime_calculated():
    log = TimeLogFactory(clock_in=time(8, 0), clock_out=time(18, 0), break_minutes=0)
    assert log.overtime_minutes == 120  # 2h prekovremeno

def test_clock_in_twice_rejected(auth_client, company, employee):
    TimeLogFactory(company=company, employee=employee, log_date=date.today(), clock_in=time(8,0))
    resp = auth_client.post("/hr/worktime/api/clock-in/", {"employee_id": str(employee.id)})
    assert resp.json()["ok"] == False
```
