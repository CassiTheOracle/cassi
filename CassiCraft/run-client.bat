@echo off
cd /d "%~dp0"
set JAVA_HOME=C:\Program Files\Zulu\zulu-25
call gradlew.bat runClient
