@echo off
REM PostgreSQL Database Backup Script for MTK Bot Order System (Windows)
REM Usage: scripts\backup_database.bat [backup_name]

setlocal enabledelayedexpansion

set BACKUP_DIR=backups

REM Get timestamp
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set TIMESTAMP=%mydate%_%mytime%

if "%1"=="" (
    set BACKUP_NAME=backup_%TIMESTAMP%
) else (
    set BACKUP_NAME=%1
)

set SERVICE=postgres
if "%DB_NAME%"=="" set DB_NAME=mtkbot
if "%DB_USER%"=="" set DB_USER=mtkbot

echo === MTK Bot Order System - PostgreSQL Backup ===
echo Service: %SERVICE%
echo Database: %DB_NAME%
echo Backup: %BACKUP_DIR%\%BACKUP_NAME%.sql
echo.

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

docker compose exec %SERVICE% pg_dump -U "%DB_USER%" "%DB_NAME%" > "%BACKUP_DIR%\%BACKUP_NAME%.sql"

echo Backup completed: %BACKUP_DIR%\%BACKUP_NAME%.sql

