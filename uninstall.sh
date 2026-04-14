#!/bin/bash

set -e
# 根据star_xxx_asr.sh文件中的实际虚拟环境名称，进行删除和卸载
#ENV_NAME="asrservice"
ENV_NAME="asrservice"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="asr-service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=========================================="
echo "        ASR Service 卸载脚本"
echo "=========================================="
echo ""
read -r -p "确认卸载 ASR Service 及相关组件？[y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消卸载"
    exit 0
fi
echo ""

# ──────────────────────────────────────────────
# 1. 停止并移除 systemd 服务
# ──────────────────────────────────────────────
if [ -f "$SERVICE_FILE" ]; then
    echo "[信息] 正在停止服务..."
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    echo "[信息] 正在禁用开机自启动..."
    sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    echo "[信息] 正在删除服务文件..."
    sudo rm -f "$SERVICE_FILE"
    sudo systemctl daemon-reload
    echo "[完成] systemd 服务已移除"
else
    echo "[跳过] 未检测到 systemd 服务，跳过"
fi

# ──────────────────────────────────────────────
# 2. 删除 conda 虚拟环境
# ──────────────────────────────────────────────
# 初始化 conda
if command -v conda &>/dev/null; then
    eval "$(conda shell.bash hook)"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
else
    echo "[跳过] 未找到 conda，跳过虚拟环境删除"
fi

if conda env list 2>/dev/null | grep -q "^${ENV_NAME} "; then
    echo "[信息] 正在删除 conda 虚拟环境 '${ENV_NAME}'..."
    conda remove -n "$ENV_NAME" --all -y
    echo "[完成] 虚拟环境已删除"
else
    echo "[跳过] 虚拟环境 '${ENV_NAME}' 不存在，跳过"
fi

# ──────────────────────────────────────────────
# 3. 可选：删除已下载的模型文件
# ──────────────────────────────────────────────
MODEL_DIR="$SCRIPT_DIR/models"
if [ -d "$MODEL_DIR" ] && [ "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
    echo ""
    read -r -p "是否同时删除已下载的模型文件（$MODEL_DIR）？[y/N] " del_model
    if [[ "$del_model" =~ ^[Yy]$ ]]; then
        rm -rf "$MODEL_DIR"
        echo "[完成] 模型文件已删除"
    else
        echo "[跳过] 保留模型文件"
    fi
fi

echo ""
echo "=========================================="
echo "         ASR Service 卸载完成"
echo "=========================================="
