@echo off
REM Windows batch equivalent of type_check.sh
REM Read from stdin (not directly supported in batch, but Claude will handle this)

cd /d "%CLAUDE_PROJECT_DIR%" || exit /b 2

REM Run TypeScript compiler check
npx --no-install tsc --noEmit 2>&1
if %errorlevel% neq 0 (
    exit /b 2
)
exit /b 0
