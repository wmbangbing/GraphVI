@echo off
cd /d D:\project\sjzl\graphvi
echo Start time: %date% %time% > scripts/vectorize_log.txt
set NEO4J_PWD=password123
set EMB_API_KEY=sk-ugxpwtjpszfvonibfbpouozefvederoanhwvgpfyvvdqtfdy
set LIMIT=200
set PATH=D:\ProgramData\miniconda3;D:\ProgramData\miniconda3\Scripts;%PATH%
python scripts/vectorize_movies.py >> scripts/vectorize_log.txt 2>&1
echo Done. Log: scripts/vectorize_log.txt
pause
