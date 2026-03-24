#!/bin/bash

set -e

ENV_NAME="asrservice"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "          ASR Service 启动脚本"
echo "=========================================="

# 检查并安装 ffmpeg
if command -v ffmpeg &>/dev/null; then
    echo "[信息] ffmpeg 已安装，跳过"
else
    echo "[信息] 未检测到 ffmpeg，正在安装..."
    sudo apt update && sudo apt install ffmpeg -y
    echo "[完成] ffmpeg 安装完成"
fi

# 初始化 conda
if command -v conda &>/dev/null; then
    eval "$(conda shell.bash hook)"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
else
    echo "[错误] 未找到 conda，请先安装 Anaconda 或 Miniconda"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "[信息] 虚拟环境 '${ENV_NAME}' 已存在，跳过创建"
else
    echo "[信息] 正在创建虚拟环境 '${ENV_NAME}' (Python 3.10)..."
    conda create -n "$ENV_NAME" python=3.10 -y
    echo "[完成] 虚拟环境创建成功"
fi

# 激活虚拟环境
echo "[信息] 正在激活虚拟环境 '${ENV_NAME}'..."
conda activate "$ENV_NAME"

cd "$SCRIPT_DIR"

# 安装依赖
echo "[信息] 正在安装依赖..."
pip install -r requirements.txt
echo "[完成] 依赖安装完成"

# 下载模型（如果尚未下载）
MODEL_DIR="$SCRIPT_DIR/models"
if [ -d "$MODEL_DIR" ] && [ "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
    echo "[信息] 检测到模型目录已存在，跳过下载"
else
    echo "[信息] 正在下载语音模型（首次运行可能较慢）..."
    python download_model.py
    echo "[完成] 模型下载完成"
fi

# 启动服务
echo ""
echo "=========================================="
echo "  正在启动 ASR 服务..."
echo "=========================================="
python app.py
