@echo off
echo Activating virtual environment...
call .\supersearch_venv\Scripts\activate

echo Setting PYTHONPATH...
set PYTHONPATH=%PYTHONPATH%;%CD%

echo Running tests...
pytest %*

echo Deactivating virtual environment...
call deactivate 