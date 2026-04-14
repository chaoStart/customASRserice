#!/bin/bash

# 自动修复 Windows CRLF 换行符，修复后重新执行
if cat "$0" | grep -qP '\r'; then
    sed -i 's/\r//' "$0"
    exec bash "$0" "$@"
fi

set -e

ENV_NAME="asrservice"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="asr-service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CONFIG_FILE="$SCRIPT_DIR/.asr_config"

echo "=========================================="
echo "          ASR Service 启动脚本"
echo "=========================================="

# ──────────────────────────────────────────────
# 选择 GPU 设备
# ──────────────────────────────────────────────
select_gpu() {
    echo ""
    echo "[GPU] 正在检测可用显卡..."

    if ! command -v nvidia-smi &>/dev/null; then
        echo "[警告] 未检测到 nvidia-smi，将使用 CPU 运行"
        CUDA_DEVICE_INDEX="cpu"
        return
    fi

    # 获取 GPU 列表：序号, 名称, 显存总量(MB), 显存空闲(MB)
    mapfile -t GPU_LIST < <(nvidia-smi --query-gpu=index,name,memory.total,memory.free \
        --format=csv,noheader,nounits 2>/dev/null)

    if [ ${#GPU_LIST[@]} -eq 0 ]; then
        echo "[警告] 未找到可用 GPU，将使用 CPU 运行"
        CUDA_DEVICE_INDEX="cpu"
        return
    fi

    echo ""
    echo "  检测到以下显卡："
    echo "  ┌──────┬────────────────────────────────────┬─────────────┬─────────────┐"
    echo "  │ 序号 │ 显卡名称                           │ 显存总量    │ 空闲显存    │"
    echo "  ├──────┼────────────────────────────────────┼─────────────┼─────────────┤"
    for entry in "${GPU_LIST[@]}"; do
        IFS=',' read -r idx name total free <<< "$entry"
        idx="${idx// /}"
        name="${name## }"
        total="${total// /}"
        free="${free// /}"
        printf "  │  %-4s│ %-34s │ %7s MB  │ %7s MB  │\n" "$idx" "$name" "$total" "$free"
    done
    echo "  └──────┴────────────────────────────────────┴─────────────┴─────────────┘"
    echo ""

    while true; do
        read -r -p "  请输入要使用的显卡序号（如 0、1、2）: " INPUT_IDX
        # 验证输入是否为有效序号
        VALID=false
        for entry in "${GPU_LIST[@]}"; do
            IDX=$(echo "$entry" | cut -d',' -f1 | tr -d ' ')
            if [ "$INPUT_IDX" = "$IDX" ]; then
                VALID=true
                break
            fi
        done
        if $VALID; then
            CUDA_DEVICE_INDEX="$INPUT_IDX"
            echo "  [确认] 已选择显卡序号: $CUDA_DEVICE_INDEX"
            break
        else
            echo "  [错误] 无效序号，请从列表中选择"
        fi
    done
}

# ──────────────────────────────────────────────
# 输入显存利用率
# ──────────────────────────────────────────────
input_memory_fraction() {
    echo ""
    echo "[GPU] 设置显存利用率上限 CUDA_MEMORY_FRACTION（范围 0~1，如 0.7 表示使用 70% 显存）"
    while true; do
        read -r -p "  请输入显存利用率（0~1）: " INPUT_FRAC
        # 用 awk 校验：是合法数字 且 0 < value <= 1
        if awk -v v="$INPUT_FRAC" 'BEGIN{ exit !(v == v+0 && v > 0 && v <= 1) }' 2>/dev/null; then
            CUDA_MEMORY_FRACTION="$INPUT_FRAC"
            echo "  [确认] 显存利用率设置为: $CUDA_MEMORY_FRACTION"
            break
        fi
        echo "  [错误] 请输入 0~1 之间的数值，如 0.7"
    done
}

# ──────────────────────────────────────────────
# 加载或创建配置文件
# ──────────────────────────────────────────────
CUDA_DEVICE_INDEX=""
CUDA_MEMORY_FRACTION=""

if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    echo ""
    echo "[配置] 已加载上次配置："
    echo "       CUDA_DEVICE_INDEX    = $CUDA_DEVICE_INDEX"
    echo "       CUDA_MEMORY_FRACTION = $CUDA_MEMORY_FRACTION"
    echo ""
    read -r -p "       是否重新配置显卡参数？[y/N] " RECONFIG
    if [[ "$RECONFIG" =~ ^[Yy]$ ]]; then
        select_gpu
        [[ "$CUDA_DEVICE_INDEX" != "cpu" ]] && input_memory_fraction || CUDA_MEMORY_FRACTION=""
        # 保存新配置
        cat > "$CONFIG_FILE" <<EOF
CUDA_DEVICE_INDEX=$CUDA_DEVICE_INDEX
CUDA_MEMORY_FRACTION=$CUDA_MEMORY_FRACTION
EOF
        echo "[配置] 新配置已保存到 $CONFIG_FILE"
    fi
else
    # 首次运行，交互选择
    select_gpu
    [[ "$CUDA_DEVICE_INDEX" != "cpu" ]] && input_memory_fraction || CUDA_MEMORY_FRACTION=""
    cat > "$CONFIG_FILE" <<EOF
CUDA_DEVICE_INDEX=$CUDA_DEVICE_INDEX
CUDA_MEMORY_FRACTION=$CUDA_MEMORY_FRACTION
EOF
    echo "[配置] 配置已保存到 $CONFIG_FILE"
fi

echo ""

# ──────────────────────────────────────────────
# 注册开机自启动（systemd）
# ──────────────────────────────────────────────
setup_autostart() {
    echo "[信息] 正在配置开机自启动..."

    # root 用户直接执行，非 root 用户使用 sudo
    if [ "$EUID" -eq 0 ]; then
        SUDO=""
    else
        SUDO="sudo"
    fi

    tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=ASR Service
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/bin/bash ${SCRIPT_DIR}/start_nano2512_asr.sh
Restart=on-failure
RestartSec=10
Environment="HOME=${HOME}"
Environment="PATH=${HOME}/miniconda3/bin:${HOME}/anaconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

[Install]
WantedBy=multi-user.target
EOF

    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME"
    echo "[完成] 已注册为系统服务，开机后将自动启动"
    echo "       查看服务状态: ${SUDO:+sudo }systemctl status ${SERVICE_NAME}"
    echo "       手动停止服务: ${SUDO:+sudo }systemctl stop ${SERVICE_NAME}"
}

if ! systemctl is-system-running &>/dev/null && ! systemctl status &>/dev/null 2>&1; then
    echo "[警告] 当前环境不支持 systemd（如 Docker/容器），跳过开机自启动配置"
elif [ -f "$SERVICE_FILE" ]; then
    echo "[信息] 开机自启动已配置，跳过注册"
else
    setup_autostart
fi

# ──────────────────────────────────────────────
# 检查并安装 ffmpeg
# ──────────────────────────────────────────────
if command -v ffmpeg &>/dev/null; then
    echo "[信息] ffmpeg 已安装，跳过"
else
    echo "[信息] 未检测到 ffmpeg，正在安装..."
    if [ "$EUID" -eq 0 ]; then
        apt update && apt install ffmpeg -y
    else
        sudo apt update && sudo apt install ffmpeg -y
    fi
    echo "[完成] ffmpeg 安装完成"
fi

# ──────────────────────────────────────────────
# 初始化 conda
# ──────────────────────────────────────────────
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

# ──────────────────────────────────────────────
# 启动服务
# ──────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  正在启动 ASR 服务..."
echo "  CUDA_DEVICE_INDEX    = $CUDA_DEVICE_INDEX"
echo "  CUDA_MEMORY_FRACTION = $CUDA_MEMORY_FRACTION"
echo "=========================================="
CUDA_DEVICE_INDEX="$CUDA_DEVICE_INDEX" \
CUDA_MEMORY_FRACTION="$CUDA_MEMORY_FRACTION" \
python app.py
