@echo off
chcp 65001 > nul
title مساعد الرسم بالقلم عبر الطابعة

echo ======================================================
echo 🖋️ جاري تشغيل مساعد الرسم بالقلم عبر الطابعة...
echo ======================================================

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 "%~dp0main.py"
    goto end
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%~dp0main.py"
    goto end
)

echo ❌ خطأ: لم يتم العثور على بايثون في جهازك!
pause

:end
if %errorlevel% neq 0 (
    echo.
    echo ❌ حدث استثناء أو خطأ أثناء تشغيل البرنامج.
    pause
)
