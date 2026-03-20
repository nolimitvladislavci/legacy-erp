@echo off
REM ═══════════════════════════════════════════════════════════
REM  LIMIT Connect POS — Kiosk Setup (Windows)
REM  Pokreni kao Administrator
REM ═══════════════════════════════════════════════════════════

SET POS_URL=https://limit-connect.com/hr/pos/quick/1/
SET CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
SET SHORTCUT=%USERPROFILE%\Desktop\POS Blagajna.lnk

echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║   LIMIT Connect POS — Kiosk Installer     ║
echo  ╚═══════════════════════════════════════════╝
echo.

REM Provjeri Chrome
if not exist %CHROME% (
    echo [!] Chrome nije pronadjen na standardnoj lokaciji.
    echo     Instalirajte Chrome ili uredite putanju u skripti.
    pause
    exit /b 1
)

REM Kreiraj shortcut s kiosk flagovima
echo [1] Kreiram precac na Desktop...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = %CHROME%; $s.Arguments = '--kiosk --kiosk-printing --disable-translate --disable-features=TranslateUI --noerrdialogs --disable-infobars --disable-session-crashed-bubble \"%POS_URL%\"'; $s.IconLocation = %CHROME%; $s.Save()"

echo [2] Precac kreiran: %SHORTCUT%
echo.
echo  ┌─────────────────────────────────────────┐
echo  │ Kiosk mod ukljucuje:                     │
echo  │ --kiosk          = Fullscreen, bez URL   │
echo  │ --kiosk-printing = Auto print (no dialog)│
echo  │ --disable-translate = Bez prevodioca     │
echo  │ --noerrdialogs   = Bez error popupa      │
echo  └─────────────────────────────────────────┘
echo.
echo [OK] Dvaput kliknite "POS Blagajna" na Desktopu za pokretanje.
echo      Za izlaz iz kiosk moda: Alt+F4
echo.
pause
