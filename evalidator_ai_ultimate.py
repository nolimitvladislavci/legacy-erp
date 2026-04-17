#!/usr/bin/env python3
"""
EVALIDATOR AI ULTIMATE - JEDNA SKRIPTA ZA SVE
Pokreni: python3 evalidator_ai_ultimate.py
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# ============================================================================
# KONFIGURACIJA
# ============================================================================

CONFIG = {
    'project_root': Path.cwd(),  # ili specificiraj: Path('/put/do/evalidator')
    'api_key': 'evalidator_ai_2024_ultimate',
    'base_url': 'https://evalidator.eu',
    'verbose': True
}

# ============================================================================
# MODUL ZA ANALIZU KODA (BEZ API POZIVA)
# ============================================================================

class CodeAnalyzer:
    """Analizira Python kod direktno, ne treba API"""
    
    @staticmethod
    def analyze_file(filepath: Path) -> Dict[str, Any]:
        """Analizira jedan Python fajl"""
        if not filepath.exists():
            return {'error': f'Fajl ne postoji: {filepath}'}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        return {
            'name': filepath.name,
            'path': str(filepath),
            'size_kb': round(len(content) / 1024, 2),
            'lines': len(lines),
            'hash': hashlib.sha256(content.encode()).hexdigest()[:16],
            'functions': CodeAnalyzer._extract_functions(content),
            'classes': CodeAnalyzer._extract_classes(content),
            'imports': CodeAnalyzer._extract_imports(content),
            'complexity': CodeAnalyzer._calculate_complexity(content),
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def _extract_functions(content: str) -> List[str]:
        pattern = r'def\s+(\w+)\s*\('
        return re.findall(pattern, content)
    
    @staticmethod
    def _extract_classes(content: str) -> List[str]:
        pattern = r'class\s+(\w+)'
        return re.findall(pattern, content)
    
    @staticmethod
    def _extract_imports(content: str) -> List[str]:
        imports = []
        # from x import y
        pattern1 = r'from\s+(\S+)\s+import'
        # import x
        pattern2 = r'^import\s+(\S+)'
        imports.extend(re.findall(pattern1, content, re.MULTILINE))
        imports.extend(re.findall(pattern2, content, re.MULTILINE))
        return list(set(imports))
    
    @staticmethod
    def _calculate_complexity(content: str) -> int:
        decisions = re.findall(r'\b(if|elif|for|while|and|or|except|finally|try)\b', content)
        return len(decisions) + 1

# ============================================================================
# AI ASISTENT ZA GENERIRANJE KODA
# ============================================================================

class AIAssistant:
    """Generira kod na temelju analize"""
    
    @staticmethod
    def generate_suggestions(analysis: Dict) -> List[Dict]:
        """Generira AI sugerencije na temelju analize"""
        suggestions = []
        
        for module in analysis.get('modules', []):
            # Visoka kompleksnost
            if module.get('complexity', 0) > 10:
                suggestions.append({
                    'type': 'refactor',
                    'module': module['name'],
                    'issue': f"Ciklomatska kompleksnost: {module['complexity']}",
                    'suggestion': 'Razbiti funkciju na manje dijelove',
                    'priority': 'HIGH',
                    'code': AIAssistant._generate_refactor_code(module)
                })
            
            # Nema docstringova
            if module.get('functions') and len(module['functions']) > 0:
                suggestions.append({
                    'type': 'documentation',
                    'module': module['name'],
                    'issue': 'Nedostaje dokumentacija',
                    'suggestion': 'Dodati docstringove za sve funkcije',
                    'priority': 'MEDIUM',
                    'code': AIAssistant._generate_docstring_template(module['functions'][0])
                })
        
        # AI integracija
        suggestions.append({
            'type': 'feature',
            'module': 'ai_integration',
            'issue': 'Nema AI endpointa',
            'suggestion': 'Implementirati /api/ai_analyze endpoint',
            'priority': 'CRITICAL',
            'code': AIAssistant._generate_ai_endpoint()
        })
        
        # Monitoring
        suggestions.append({
            'type': 'monitoring',
            'module': 'health_check',
            'issue': 'Nema health checka',
            'suggestion': 'Dodati /health endpoint za monitoring',
            'priority': 'HIGH',
            'code': AIAssistant._generate_health_endpoint()
        })
        
        return suggestions
    
    @staticmethod
    def _generate_refactor_code(module: Dict) -> str:
        return f'''
# REFAKTORIRAN MODUL: {module['name']}
# Originalna kompleksnost: {module.get('complexity', '?')}

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
    return {{'status': 'processed', 'data': data}}

def _format_output(result):
    """Formatiranje izlaza"""
    return {{
        'timestamp': datetime.now().isoformat(),
        'result': result
    }}
'''
    
    @staticmethod
    def _generate_docstring_template(function_name: str) -> str:
        return f'''
def {function_name}(param1, param2=None):
    """
    {function_name.replace('_', ' ').title()}
    
    Args:
        param1: Opis prvog parametra
        param2: Opis drugog parametra (opcijski)
    
    Returns:
        dict: Opis povratne vrijednosti
    
    Raises:
        ValueError: Ako param1 nije validan
    
    Example:
        >>> {function_name}("test")
        {{'status': 'success'}}
    """
    pass
'''
    
    @staticmethod
    def _generate_ai_endpoint() -> str:
        return '''
# AI ENDPOINT - Dodaj u evalidator/urls.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(['POST'])
def ai_analyze_endpoint(request):
    """
    AI endpoint za analizu sustava
    """
    try:
        data = json.loads(request.body)
        
        # Analiza koda
        analysis = {
            'status': 'ok',
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'ai_ready': True,
            'suggestions': [
                'Dodati caching za bolje performanse',
                'Implementirati rate limiting',
                'Koristiti async/await za I/O operacije'
            ]
        }
        
        return JsonResponse(analysis)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Dodaj u urlpatterns:
# path('api/ai_analyze/', ai_analyze_endpoint),
'''
    
    @staticmethod
    def _generate_health_endpoint() -> str:
        return '''
# HEALTH CHECK ENDPOINT - Dodaj u evalidator/urls.py
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError

def health_check(request):
    """
    Health check endpoint za monitoring
    """
    health = {
        'status': 'healthy',
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'checks': {}
    }
    
    # Provjera baze
    try:
        connections['default'].cursor()
        health['checks']['database'] = 'ok'
    except OperationalError:
        health['status'] = 'unhealthy'
        health['checks']['database'] = 'error'
    
    # Provjera diska
    import shutil
    disk = shutil.disk_usage('/')
    health['checks']['disk'] = {
        'free_gb': round(disk.free / (1024**3), 2),
        'percent_free': round(disk.free / disk.total * 100, 2)
    }
    
    return JsonResponse(health)

# Dodaj u urlpatterns:
# path('health/', health_check),
'''

# ============================================================================
# GLAVNI PROGRAM
# ============================================================================

class EvalidatorUltimate:
    """Glavna klasa koja sve pokreće"""
    
    def __init__(self):
        self.analyzer = CodeAnalyzer()
        self.assistant = AIAssistant()
        self.results = {}
    
    def find_python_files(self) -> List[Path]:
        """Pronalazi sve Python fajlove u projektu"""
        python_files = []
        root = CONFIG['project_root']
        
        # Poznati putevi za evalidator
        possible_paths = [
            root / 'evalidator',
            root / 'ev',
            root / 'app',
            root / 'evapi',
            root,
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_dir():
                for py_file in path.rglob('*.py'):
                    if 'venv' not in str(py_file) and '__pycache__' not in str(py_file):
                        python_files.append(py_file)
        
        # Ako nema fajlova, kreiraj demo strukturu
        if not python_files:
            print("\n⚠️ Nema Python fajlova, kreiram demo strukturu...")
            self._create_demo_structure()
            python_files = list((root / 'evalidator_demo').rglob('*.py'))
        
        return python_files
    
    def _create_demo_structure(self):
        """Kreira demo fajlove za testiranje"""
        demo_dir = CONFIG['project_root'] / 'evalidator_demo'
        demo_dir.mkdir(exist_ok=True)
        
        demo_code = '''
# evalidator.py - Demo modul za analizu
import hashlib
import json
from datetime import datetime

class Validator:
    def validate_document(self, doc_hash):
        if not doc_hash:
            return {'error': 'No hash provided'}
        
        if len(doc_hash) != 64:
            return {'error': 'Invalid hash length'}
        
        result = self._check_database(doc_hash)
        
        if result:
            return {'valid': True, 'timestamp': datetime.now().isoformat()}
        else:
            return {'valid': False, 'message': 'Document not found'}
    
    def _check_database(self, doc_hash):
        # Simulacija baze
        return doc_hash.startswith('abc')
    
    def cross_validate(self, doc_hash, source):
        if source == 'evalidator':
            return self.validate_document(doc_hash)
        elif source == 'notary':
            return self._notary_check(doc_hash)
        else:
            return {'error': 'Unknown source'}
    
    def _notary_check(self, doc_hash):
        return {'valid': True, 'notary_seal': 'sealed'}

# Glavna funkcija
def main():
    v = Validator()
    result = v.validate_document('abc123...')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
'''
        
        with open(demo_dir / 'evalidator.py', 'w') as f:
            f.write(demo_code)
        
        print(f"✅ Kreirana demo struktura u {demo_dir}")
    
    def analyze_all(self):
        """Analizira sve fajlove"""
        print("\n" + "="*60)
        print(" EVALIDATOR AI ULTIMATE - ANALIZA SUSTAVA")
        print("="*60)
        print(f"📁 Projektni root: {CONFIG['project_root']}")
        print(f"⏰ Vrijeme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        python_files = self.find_python_files()
        print(f"📄 Pronađeno Python fajlova: {len(python_files)}")
        
        modules = []
        for filepath in python_files:
            print(f"   🔍 Analiziram: {filepath.relative_to(CONFIG['project_root'])}")
            analysis = self.analyzer.analyze_file(filepath)
            modules.append(analysis)
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'total_files': len(modules),
            'total_lines': sum(m.get('lines', 0) for m in modules),
            'avg_complexity': sum(m.get('complexity', 0) for m in modules) / len(modules) if modules else 0,
            'modules': modules
        }
        
        return self.results
    
    def generate_report(self, analysis: Dict) -> str:
        """Generira čitljiv izvještaj"""
        report = []
        report.append("\n" + "="*60)
        report.append("📊 IZVJEŠTAJ ANALIZE")
        report.append("="*60)
        
        report.append(f"\n📈 Statistika:")
        report.append(f"   - Ukupno fajlova: {analysis['total_files']}")
        report.append(f"   - Ukupno linija koda: {analysis['total_lines']}")
        report.append(f"   - Prosječna kompleksnost: {analysis['avg_complexity']:.1f}")
        
        report.append(f"\n📁 Detalji po modulima:")
        for module in analysis['modules']:
            status = "✅" if module['complexity'] <= 10 else "⚠️"
            report.append(f"   {status} {module['name']}: {module['lines']} linija, {module['functions']} funkcija, kompleksnost {module['complexity']}")
        
        # AI Sugestije
        suggestions = self.assistant.generate_suggestions(analysis)
        
        report.append(f"\n🤖 AI SUGESTIJE ({len(suggestions)}):")
        for i, sug in enumerate(suggestions, 1):
            priority_icon = "🔴" if sug['priority'] == 'CRITICAL' else "🟡" if sug['priority'] == 'HIGH' else "🟢"
            report.append(f"\n   {priority_icon} {i}. {sug['type'].upper()}: {sug['suggestion']}")
            report.append(f"      📁 Modul: {sug['module']}")
            report.append(f"      🐛 Problem: {sug['issue']}")
        
        return "\n".join(report)
    
    def save_suggestions(self, suggestions: List[Dict]):
        """Sprema AI generirani kod u fajlove"""
        output_dir = CONFIG['project_root'] / 'ai_generated'
        output_dir.mkdir(exist_ok=True)
        
        for sug in suggestions:
            filename = f"{sug['type']}_{sug['module'].replace('.py', '')}.py"
            filepath = output_dir / filename
            
            with open(filepath, 'w') as f:
                f.write(f"# AI GENERATED: {sug['suggestion']}\n")
                f.write(f"# Priority: {sug['priority']}\n")
                f.write(f"# Issue: {sug['issue']}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                f.write(sug.get('code', '# Kod nije generiran\n'))
            
            print(f"   💾 Spremljeno: {filepath}")
    
    def run_continuous(self):
        """Kontinuirano praćenje"""
        print("\n" + "="*60)
        print("🔄 KONTINUIRANO PRAĆENJE (Ctrl+C za prekid)")
        print("="*60)
        
        iteration = 0
        try:
            while True:
                iteration += 1
                print(f"\n📡 Iteracija {iteration} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Analiza
                analysis = self.analyze_all()
                
                # Generiranje sugestija
                suggestions = self.assistant.generate_suggestions(analysis)
                critical = [s for s in suggestions if s['priority'] == 'CRITICAL']
                high = [s for s in suggestions if s['priority'] == 'HIGH']
                
                print(f"   🔴 Kritičnih: {len(critical)}")
                print(f"   🟡 Visokih: {len(high)}")
                print(f"   🟢 Ostalih: {len(suggestions) - len(critical) - len(high)}")
                
                if critical:
                    print(f"\n   ⚠️ HITNE AKCIJE:")
                    for sug in critical:
                        print(f"      - {sug['suggestion']}")
                
                # Čekanje
                import time
                time.sleep(60)  # Provjera svake minute
                
        except KeyboardInterrupt:
            print("\n\n✅ Zaustavljeno praćenje")
    
    def main(self):
        """Glavna metoda"""
        print("\n🚀 Pokrećem Evalidator AI Ultimate...")
        
        # 1. Analiza
        analysis = self.analyze_all()
        
        # 2. Prikaz izvještaja
        report = self.generate_report(analysis)
        print(report)
        
        # 3. Generiranje sugestija
        print("\n" + "="*60)
        print("🤖 GENERIRAM AI KOD")
        print("="*60)
        suggestions = self.assistant.generate_suggestions(analysis)
        self.save_suggestions(suggestions)
        
        # 4. Upute
        print("\n" + "="*60)
        print("📋 SLJEDEĆI KORACI")
        print("="*60)
        print("""
1. Pregledaj generirani kod u mapi 'ai_generated/'
2. Kopiraj predložene endpoint-e u evalidator/urls.py
3. Pokreni testove: python manage.py test
4. Za kontinuirano praćenje pokreni: --watch
        """)
        
        # 5. Spremanje kompletnog izvještaja
        report_file = CONFIG['project_root'] / 'ai_analysis_report.json'
        with open(report_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"📄 Kompletan izvještaj spremljen u: {report_file}")
        
        print("\n✅ ZAVRŠENO! AI asistent je spreman.")
        
        return analysis

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Evalidator AI Ultimate')
    parser.add_argument('--watch', action='store_true', help='Kontinuirano praćenje')
    parser.add_argument('--path', type=str, help='Putanja do projekta')
    args = parser.parse_args()
    
    if args.path:
        CONFIG['project_root'] = Path(args.path)
    
    app = EvalidatorUltimate()
    
    if args.watch:
        app.run_continuous()
    else:
        app.main()
