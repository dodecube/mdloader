@echo off
REM Wrapper: Windows native messaging hosts must be an .exe/.bat, not a .py file.
REM Adjust PYTHONW/python path below if python is not on PATH.
python "%~dp0..\msg.py"
