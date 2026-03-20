# Ctrl+X, Y, Enter
#!/usr/bin/env python3
"""
🔍 PORTAL AUDIT SCRIPT
Analizira trenutno stanje Django projekta
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

class PortalAuditor:
    def __init__(self):
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(Path.cwd()),
            'sections': {}
        }
        self.output = []
    
    def header(self, text, emoji='🔍'):
        line = f"\n{'='*80}\n{emoji} {text}\n{'='*80}"
        self.output.append(line)
        print(line)
    
    def info(self, text):
        self.output.append(text)
        print(text)
    
    def run_command(self, cmd, shell=True):
        """Run shell command and return output"""
        try:
            result = subprocess.run(
                cmd, 
                shell=shell, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def check_1_structure(self):
        """1️⃣ Struktura projekta"""
        self.header("1️⃣ STRUKTURA PROJEKTA", "📁")
        
        # Find Django project
        manage_py = Path('manage.py')
        if not manage_py.exists():
            self.info("❌ manage.py not found!")
            return
        
        # Tree structure
        tree_cmd = "tree -L 3 -I '__pycache__|*.pyc|venv|env|node_modules|staticfiles|media' --dirsfirst"
        tree_output = self.run_command(tree_cmd)
        
        if "command not found" in tree_output:
            # Fallback to find
            tree_output = self.run_command("find . -maxdepth 3 -type d | grep -v '__pycache__\\|.git\\|venv\\|env'")
        
        self.info(tree_output)
        self.report['sections']['structure'] = tree_output
        
        # Find all Python apps
        self.info("\n📦 Django Apps:")
        apps = []
        for path in Path('.').rglob('models.py'):
            app_path = path.parent
            if '__pycache__' not in str(app_path):
                apps.append(str(app_path))
                self.info(f"  ✓ {app_path}")
        
        self.report['sections']['apps'] = apps
    
    def check_2_installed_apps(self):
        """2️⃣ INSTALLED_APPS"""
        self.header("2️⃣ INSTALLED_APPS & SETTINGS", "⚙️")
        
        # Find settings files
        settings_files = list(Path('.').rglob('settings.py')) + list(Path('.').rglob('settings/*.py'))
        
        for settings_file in settings_files:
            if '__pycache__' in str(settings_file):
                continue
            
            self.info(f"\n📄 {settings_file}")
            self.info("-" * 80)
            
            try:
                content = settings_file.read_text()
                
                # Extract INSTALLED_APPS
                if 'INSTALLED_APPS' in content:
                    start = content.find('INSTALLED_APPS')
                    end = content.find(']', start) + 1
                    apps_section = content[start:end]
                    self.info("INSTALLED_APPS:")
                    self.info(apps_section[:1000])  # First 1000 chars
                
                # Extract AUTH_USER_MODEL
                if 'AUTH_USER_MODEL' in content:
                    for line in content.split('\n'):
                        if 'AUTH_USER_MODEL' in line and not line.strip().startswith('#'):
                            self.info(f"\n🔐 {line.strip()}")
                
                # Extract DATABASES
                if 'DATABASES' in content:
                    start = content.find('DATABASES')
                    end = content.find('}', start) + 1
                    # Find closing brace properly
                    brace_count = 0
                    for i, char in enumerate(content[start:], start):
                        if char == '{': brace_count += 1
                        if char == '}': brace_count -= 1
                        if brace_count == 0 and char == '}':
                            end = i + 1
                            break
                    db_section = content[start:end]
                    self.info(f"\n💾 DATABASE:")
                    self.info(db_section[:500])
                
            except Exception as e:
                self.info(f"❌ Error reading {settings_file}: {e}")
    
    def check_3_models(self):
        """3️⃣ User models & all models"""
        self.header("3️⃣ MODELS (User + Sve ostale)", "🗄️")
        
        model_files = list(Path('.').rglob('models.py'))
        
        for model_file in model_files:
            if '__pycache__' in str(model_file):
                continue
            
            self.info(f"\n📄 {model_file}")
            self.info("-" * 80)
            
            try:
                content = model_file.read_text()
                
                # Find all model classes
                models = []
                for line in content.split('\n'):
                    if 'class ' in line and '(models.Model)' in line or '(AbstractUser)' in line or '(AbstractBaseUser)' in line:
                        models.append(line.strip())
                
                if models:
                    self.info("📊 Models found:")
                    for model in models:
                        self.info(f"  • {model}")
                    
                    # Show User/UserProfile details
                    if 'User' in content or 'UserProfile' in content:
                        self.info("\n👤 User Model Details:")
                        self.info(content[:2000])  # First 2000 chars
                else:
                    self.info("  (no models)")
                    
            except Exception as e:
                self.info(f"❌ Error: {e}")
    
    def check_4_migrations(self):
        """4️⃣ Database migrations"""
        self.header("4️⃣ DATABASE & MIGRATIONS", "🗃️")
        
        # Show migrations
        self.info("📊 Current migrations status:\n")
        migrations = self.run_command("python manage.py showmigrations")
        self.info(migrations)
        
        # Inspect DB schema
        self.info("\n📋 Database schema inspection:\n")
        inspect = self.run_command("python manage.py inspectdb")
        
        # Save to file
        if inspect and '❌' not in inspect:
            schema_file = Path('current_schema.txt')
            schema_file.write_text(inspect)
            self.info(f"✅ Full schema saved to: {schema_file}")
            self.info(f"\n{inspect[:3000]}...")  # Show first 3000 chars
        else:
            self.info(inspect)
    
    def check_5_dependencies(self):
        """5️⃣ Dependencies & packages"""
        self.header("5️⃣ DEPENDENCIES & PACKAGES", "📦")
        
        # requirements.txt
        req_files = ['requirements.txt', 'requirements/base.txt', 'requirements/production.txt']
        
        for req_file in req_files:
            req_path = Path(req_file)
            if req_path.exists():
                self.info(f"\n📄 {req_file}")
                self.info("-" * 80)
                content = req_path.read_text()
                self.info(content)
        
        # Installed packages
        self.info("\n📦 Currently installed packages:\n")
        packages = self.run_command("pip list --format=freeze")
        self.info(packages)
    
    def check_6_urls(self):
        """6️⃣ URL patterns"""
        self.header("6️⃣ URL PATTERNS", "🔗")
        
        url_files = list(Path('.').rglob('urls.py'))
        
        for url_file in url_files:
            if '__pycache__' in str(url_file):
                continue
            
            self.info(f"\n📄 {url_file}")
            self.info("-" * 80)
            
            try:
                content = url_file.read_text()
                self.info(content)
            except Exception as e:
                self.info(f"❌ Error: {e}")
    
    def check_7_views(self):
        """7️⃣ Views summary"""
        self.header("7️⃣ VIEWS & LOGIC", "👁️")
        
        view_files = list(Path('.').rglob('views.py'))
        
        for view_file in view_files:
            if '__pycache__' in str(view_file):
                continue
            
            self.info(f"\n📄 {view_file}")
            self.info("-" * 80)
            
            try:
                content = view_file.read_text()
                
                # Find all function/class views
                views = []
                for line in content.split('\n'):
                    if line.startswith('def ') or (line.startswith('class ') and 'View' in line):
                        views.append(line.strip())
                
                if views:
                    self.info("🎯 Views found:")
                    for view in views:
                        self.info(f"  • {view}")
                else:
                    self.info("  (no views)")
                    
            except Exception as e:
                self.info(f"❌ Error: {e}")
    
    def save_report(self):
        """Save report to files"""
        self.header("💾 SAVING REPORT", "💾")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save text report
        txt_file = f"audit_report_{timestamp}.txt"
        Path(txt_file).write_text('\n'.join(self.output))
        self.info(f"✅ Text report: {txt_file}")
        
        # Save JSON report
        json_file = f"audit_report_{timestamp}.json"
        Path(json_file).write_text(json.dumps(self.report, indent=2, ensure_ascii=False))
        self.info(f"✅ JSON report: {json_file}")
        
        self.info(f"\n🎉 Audit complete! Check the files above.")
    
    def run(self):
        """Run full audit"""
        self.header("🚀 PORTAL AUDIT STARTED", "🚀")
        self.info(f"📅 Time: {self.report['timestamp']}")
        self.info(f"📁 Directory: {self.report['project_root']}")
        
        try:
            self.check_1_structure()
            self.check_2_installed_apps()
            self.check_3_models()
            self.check_4_migrations()
            self.check_5_dependencies()
            self.check_6_urls()
            self.check_7_views()
            self.save_report()
        except KeyboardInterrupt:
            self.info("\n\n⚠️ Audit interrupted by user")
        except Exception as e:
            self.info(f"\n\n❌ Fatal error: {e}")
            import traceback
            self.info(traceback.format_exc())


if __name__ == '__main__':
    auditor = PortalAuditor()
    auditor.run()

