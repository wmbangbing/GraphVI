#!/bin/bash
# GraphVI 启动脚本（Linux / macOS）
# 用法: ./start.sh [port]

PORT=${1:-8000}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

echo "==================================="
echo "  GraphVI — 知识图谱可视化查询系统"
echo "==================================="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 未安装，请先安装 Python 3.10+"
    exit 1
fi

# Activate virtualenv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "[INFO] 已激活虚拟环境 venv"
fi

echo "[INFO] 启动服务，端口: $PORT"
echo "[INFO] 浏览器访问: http://localhost:$PORT"
echo ""

python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" --log-level info
