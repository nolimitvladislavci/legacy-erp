import os

# Putanja projekta
root_dir = '/var/www/fina-connect'

# Popis "mrtvih" migracija koje ostali moduli traže, a više ne postoje
ghost_migrations = [
    "('companies', '0001_initial')",
    "('partners', '0001_initial')",
    "('documents', '0001_initial')",
    "('finance', '0001_initial')",
]

print(">>> Skeniram sve module za neispravnim vezama...")

for subdir, dirs, files in os.walk(root_dir):
    # Gledamo samo unutar 'migrations' foldera
    if 'migrations' in subdir:
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                filepath = os.path.join(subdir, file)
                
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                
                new_lines = []
                modified = False
                
                for line in lines:
                    # Ako linija sadrži referencu na mrtvu migraciju, preskačemo je
                    if any(ghost in line for ghost in ghost_migrations):
                        print(f"   [FIX] Čistim datoteku: {filepath}")
                        print(f"         Uklonjeno: {line.strip()}")
                        modified = True
                    else:
                        new_lines.append(line)
                
                # Spremamo samo ako smo nešto mijenjali
                if modified:
                    with open(filepath, 'w') as f:
                        f.writelines(new_lines)

print(">>> Čišćenje završeno.")
