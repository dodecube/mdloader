@echo off
REM Windows native messaging hosts must be an .exe/.bat, never a bare .py file.
REM Set MDLOADER_PYTHON if python is not on PATH, e.g. C:\Python312\pythonw.exe
if "%MDLOADER_PYTHON%"=="" set "MDLOADER_PYTHON=python"
"%MDLOADER_PYTHON%" "%~dp0..\host" %*
