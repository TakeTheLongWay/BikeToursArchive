@echo off
REM Pfad zu deinem Python-Interpreter in der virtuellen Umgebung
set PYTHONPATH=C:\Users\Markus\PycharmProjects\GPSTracks\.venv\Scripts\python.exe

REM Flask App starten
%PYTHONPATH% app.py

chrome http://127.0.0.1:5000

pause

