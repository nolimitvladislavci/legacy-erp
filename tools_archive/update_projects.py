import os

file_path = 'projects/models.py'
with open(file_path, 'r') as f:
    content = f.read()

# Definiramo novu metodu
new_method = """
    @property
    def budget_usage_percentage(self):
        try:
            from work_time.models import TimeEntry
            total_cost = 0
            entries = TimeEntry.objects.filter(project=self)
            for entry in entries:
                # Koristimo tvoju strukturu: user -> userprofile -> hourly_rate
                rate = entry.user.userprofile.hourly_rate or 0
                total_cost += (entry.duration_hours * rate)
            
            if self.budget > 0:
                return round((total_cost / float(self.budget)) * 100, 2)
            return 0
        except:
            return 0
"""

# Umećemo metodu unutar klase Project (tražimo kraj definicije polja)
if 'budget_usage_percentage' not in content:
    updated_content = content.replace('updated_at = ', 'updated_at = models.DateTimeField(auto_now=True)\n' + new_method, 1)
    with open(file_path, 'w') as f:
        f.write(updated_content)
    print("Metoda uspješno dodana u Project model!")
else:
    print("Metoda već postoji.")
