@echo off
REM PostgreSQL Database Backup Script for MTK Bot Order System (Windows)
REM Usage: scripts\backup_database.bat [dev|prod] [backup_name]

setlocal enabledelayedexpansion

set ENVIRONMENT=%1
if "%ENVIRONMENT%"=="" set ENVIRONMENT=dev

set BACKUP_DIR=backups

REM Get timestamp
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set TIMESTAMP=%mydate%_%mytime%

if "%2"=="" (
    set BACKUP_NAME=backup_%ENVIRONMENT%_%TIMESTAMP%
) else (
    set BACKUP_NAME=%2
)

if "%ENVIRONMENT%"=="prod" (
    set SERVICE=postgres-prod
    if "%PROD_DB_NAME%"=="" set PROD_DB_NAME=mtkbot_prod
    if "%PROD_DB_USER%"=="" set PROD_DB_USER=mtkbot_prod
    set DB_NAME=%PROD_DB_NAME%
    set DB_USER=%PROD_DB_USER%
) else (
    set SERVICE=postgres-dev
    if "%DEV_DB_NAME%"=="" set DEV_DB_NAME=mtkbot_dev
    if "%DEV_DB_USER%"=="" set DEV_DB_USER=mtkbot_dev
    set DB_NAME=%DEV_DB_NAME%
    set DB_USER=%DEV_DB_USER%
)

echo === MTK Bot Order System - PostgreSQL Backup (%ENVIRONMENT%) ===
echo Service: %SERVICE%
echo Database: %DB_NAME%
echo Backup: %BACKUP_DIR%\%BACKUP_NAME%.sql
echo.

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

docker compose exec %SERVICE% pg_dump -U "%DB_USER%" "%DB_NAME%" > "%BACKUP_DIR%\%BACKUP_NAME%.sql"

echo Backup completed: %BACKUP_DIR%\%BACKUP_NAME%.sql

