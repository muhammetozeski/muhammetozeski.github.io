@echo off
chcp 65001 >nul
setlocal
rem --- HTML dosyalarini gercek tek-sayfa PDF'e cevirir ---
rem Kullanim 1: bir veya birden fazla .html dosyasini bu .bat uzerine surukleyip birak.
rem Kullanim 2: komut satiri ->  "HTML to PDF.bat" "dosya.html"

if "%~1"=="" (
  echo.
  echo   HTML to PDF
  echo   -----------
  echo   Bir veya birden fazla .html dosyasini bu pencerenin / .bat dosyasinin uzerine
  echo   surukleyip birakin. Her .html yaninda ayni adla .pdf olusur.
  echo.
  echo   Komut satiri:  "HTML to PDF.bat" "C:\yol\dosya.html"
  echo.
  pause
  exit /b 0
)

python "%~dp0html2pdf.py" %*
echo.
echo Bitti.
pause
