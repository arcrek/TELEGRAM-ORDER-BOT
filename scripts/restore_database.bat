@echo off
REM PostgreSQL Database Restore Script for MTK Bot Order System (Windows)
REM Usage: scripts\restore_database.bat <backup_file.sql>

setlocal

set BACKUP_FILE=%1

echo === MTK Bot Order System - PostgreSQL Restore ===
echo.

if "%BACKUP_FILE%"=="" (
    echo [ERROR] Backup file not specified
    echo Usage: %0 ^<backup_file.sql^>
    exit /b 1
)

if not exist "%BACKUP_FILE%" (
    echo [ERROR] Backup file '%BACKUP_FILE%' not found
    exit /b 1
)

set SERVICE=postgres
if "%DB_NAME%"=="" set DB_NAME=mtkbot
if "%DB_USER%"=="" set DB_USER=mtkbot

echo Service: %SERVICE%
echo Database: %DB_NAME%
echo Backup file: %BACKUP_FILE%
echo WARNING: This will replace the current database!
set /p CONFIRM=Are you sure you want to continue? (yes/no): 

if /I not "%CONFIRM%"=="yes" (
    echo Restore cancelled
    exit /b 0
)

echo.
echo Stopping services...
docker compose stop bot bot_supplier api

echo Restoring database...

for %%F in ("%BACKUP_FILE%") do (
    set BACKUP_DIR=%%~dpF
    set BACKUP_NAME=%%~nxF
)

docker compose exec %SERVICE% bash -c "psql -U \"%DB_USER%\" -d \"%DB_NAME%\" -f \"/backup/%BACKUP_NAME%\"" -v "%BACKUP_DIR%:/backup"

echo [SUCCESS] Database restored successfully!
echo.
echo Starting services...
docker compose up -d

echo.
echo Done! Services are starting up...
echo Wait a few seconds for services to be ready.

