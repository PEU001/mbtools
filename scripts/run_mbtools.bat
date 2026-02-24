
@echo off
setlocal
set ROOT=%~dp0..
if exist %ROOT%\.venv\Scriptsctivate.bat call %ROOT%\.venv\Scriptsctivate.bat
set PYTHONPATH=%ROOT%\src;%PYTHONPATH%
python -m mbtools %1 --ua "PierreTools/1.0 (pierre@example.com)" --search-fallback --cache
