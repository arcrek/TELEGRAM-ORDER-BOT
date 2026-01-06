@echo off
REM Database Backup Script for MTK Bot Order System (Windows)
REM Usage: scripts\backup_database.bat [backup_name]

setlocal enabledelayedexpansion

set BACKUP_DIR=backups
set VOLUME_NAME=database-data

REM Get timestamp
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set TIMESTAMP=%mydate%_%mytime%

if "%1"=="" (
    set BACKUP_NAME=backup_%TIMESTAMP%
) else (
    set BACKUP_NAME=%1
)

echo === MTK Bot Order System - Database Backup ===
echo.

REM Create backup directory
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo Backing up database...
echo Volume: %VOLUME_NAME%
echo Backup: %BACKUP_DIR%\%BACKUP_NAME%.db
echo.

REM Create backup using a temporary container
docker run --rm -v %VOLUME_NAME%:/data -v "%CD%\%BACKUP_DIR%:/backup" busybox cp /data/database.db /backup/%BACKUP_NAME%.db

if exist "%BACKUP_DIR%\%BACKUP_NAME%.db" (
    echo [SUCCESS] Backup completed successfully!
    echo   File: %BACKUP_DIR%\%BACKUP_NAME%.db
    echo.
    echo Available backups:
    dir /b "%BACKUP_DIR%\*.db"
) else (
    echo [ERROR] Backup failed!
    exit /b 1
)

echo.
echo Done!

