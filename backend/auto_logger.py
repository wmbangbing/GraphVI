"""Auto analyze debug logging helper."""
import os
import json
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(__file__), "_auto_logs")
os.makedirs(_LOG_DIR, exist_ok=True)

def _ts():
    return datetime.now().strftime("%H%M%S%f")

def log_script_prompt(prompt: str):
    ts = _ts()
    path = os.path.join(_LOG_DIR, f"01_script_prompt_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"[auto_log] 脚本提示词 -> {path}", flush=True)

def log_generated_script(script: str):
    ts = _ts()
    path = os.path.join(_LOG_DIR, f"02_generated_script_{ts}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"[auto_log] 生成脚本 -> {path}", flush=True)

def log_script_result(result: dict):
    ts = _ts()
    path = os.path.join(_LOG_DIR, f"03_script_result_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[auto_log] 脚本结果 -> {path}", flush=True)

def log_fallback_stats(stats: dict):
    ts = _ts()
    path = os.path.join(_LOG_DIR, f"03_fallback_stats_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"[auto_log] 降级统计 -> {path}", flush=True)

def log_text_prompt(prompt: str):
    ts = _ts()
    path = os.path.join(_LOG_DIR, f"04_text_prompt_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"[auto_log] 总结提示词 -> {path}", flush=True)

def log_text_result(text: str):
    ts = _ts()
    path = os.path.join(_LOG_DIR, f"05_text_result_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[auto_log] 总结结果 -> {path}", flush=True)
