@echo off
REM Database Restore Script for MTK Bot Order System (Windows)
REM Usage: scripts\restore_database.bat <backup_file>

setlocal

set VOLUME_NAME=database-data

echo === MTK Bot Order System - Database Restore ===
echo.

if "%1"=="" (
    echo [ERROR] Backup file not specified
    echo Usage: %0 ^<backup_file^>
    echo.
    echo Available backups:
    dir /b "backups\*.db" 2>nul
    exit /b 1
)

set BACKUP_FILE=%1

if not exist "%BACKUP_FILE%" (
    echo [ERROR] Backup file '%BACKUP_FILE%' not found
    exit /b 1
)

echo WARNING: This will replace the current database!
echo Backup file: %BACKUP_FILE%
echo.
set /p CONFIRM=Are you sure you want to continue? (yes/no): 

if not "%CONFIRM%"=="yes" (
    echo Restore cancelled
    exit /b 0
)

echo.
echo Stopping services...
docker compose stop bot bot_supplier api

echo Restoring database...

REM Get backup directory and filename
for %%F in ("%BACKUP_FILE%") do (
    set BACKUP_DIR=%%~dpF
    set BACKUP_NAME=%%~nxF
)

REM Restore backup
docker run --rm -v %VOLUME_NAME%:/data -v "%BACKUP_DIR%:/backup" busybox cp /backup/%BACKUP_NAME% /data/database.db

echo [SUCCESS] Database restored successfully!
echo.
echo Starting services...
docker compose up -d

echo.
echo Done! Services are starting up...
echo Wait a few seconds for services to be ready.

