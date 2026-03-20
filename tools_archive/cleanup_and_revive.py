import os
import subprocess

print("🧹 ČIŠĆENJE: Ubijanje zombie procesa i oslobađanje porta 8000...")

# 1. Pronalaženje PID-a koji drži port 8000
try:
    pid_output = subprocess.check_output("lsof -t -i:8000", shell=True).decode().strip()
    if pid_output:
        pids = pid_output.split('\n')
        for pid in pids:
            print(f"🚫 Ubijam blokirajući proces PID: {pid}")
            os.system(f"kill -9 {pid}")
    else:
        print("✅ Port 8000 je već slobodan.")
except subprocess.CalledProcessError:
    print("✅ Nema aktivnih procesa na portu 8000.")

# 2. Prisilni restart Supervisora
print("🔄 Prisilno pokretanje fina-connect servisa...")
os.system("supervisorctl reread")
os.system("supervisorctl update")
os.system("supervisorctl restart fina-connect")

# 3. Provjera statusa
print("\n📊 TRENUTNI STATUS SERVISA:")
os.system("supervisorctl status fina-connect")

print("\n✨ Port je čist. Ako je status RUNNING, tvoj Premium portal je sada ONLINE.")
