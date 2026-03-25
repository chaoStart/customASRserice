#!/bin/bash

HOST="http://127.0.0.1:8000"
ENDPOINT="/asr/wav_to_text_binary"
URL="${HOST}${ENDPOINT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_WAV="$SCRIPT_DIR/weather_nice.wav"
PASS=0
FAIL=0

# 颜色
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
NC="\033[0m"

pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASS++)); }
fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAIL++)); }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

echo "=========================================="
echo "         ASR Service 测试脚本"
echo "  目标地址: $URL"
echo "=========================================="
echo ""

# ──────────────────────────────────────────────
# TEST 1: 服务存活检测（端口连通性）
# ──────────────────────────────────────────────
info "TEST 1: 检测服务是否在线..."
if curl -sf --max-time 5 "${HOST}/docs" > /dev/null 2>&1; then
    pass "服务已启动，端口 8000 可访问"
else
    fail "无法连接到 ${HOST}，请确认 start.sh 已成功执行"
    echo ""
    echo "提示：可通过以下命令查看服务状态："
    echo "  sudo systemctl status asr-service"
    echo "  sudo journalctl -u asr-service -f"
    exit 1
fi
echo ""

# ──────────────────────────────────────────────
# TEST 2: 检查测试 WAV 文件是否存在
# ──────────────────────────────────────────────
info "TEST 2: 检查测试音频文件 weather_nice.wav..."
if [ -f "$TEST_WAV" ]; then
    SIZE=$(du -h "$TEST_WAV" | cut -f1)
    pass "测试文件存在：$TEST_WAV（$SIZE）"
else
    fail "未找到测试文件：$TEST_WAV"
    exit 1
fi
echo ""

# ──────────────────────────────────────────────
# TEST 3: 正常识别请求（weather_nice.wav）
# ──────────────────────────────────────────────
info "TEST 3: 发送 weather_nice.wav 进行语音识别..."
RESPONSE=$(curl -sf --max-time 60 -X POST "$URL" \
    -F "file=@${TEST_WAV};type=audio/wav" 2>&1)
CURL_EXIT=$?

if [ $CURL_EXIT -ne 0 ]; then
    fail "请求失败（curl 退出码: $CURL_EXIT）"
else
    SUCCESS=$(echo "$RESPONSE" | grep -o '"success":true' || true)
    TEXT=$(echo "$RESPONSE" | grep -o '"text":"[^"]*"' | sed 's/"text":"//;s/"//' || true)
    if [ -n "$SUCCESS" ]; then
        pass "语音识别成功"
        echo "        响应内容: $RESPONSE"
        echo "        识别文本: $TEXT"
    else
        fail "响应中未包含 success:true"
        echo "        原始响应: $RESPONSE"
    fi
fi
echo ""

# ──────────────────────────────────────────────
# TEST 4: 非 WAV 文件格式拒绝校验
# ──────────────────────────────────────────────
info "TEST 4: 上传非 WAV 文件，验证服务是否正确拒绝..."
FAKE_FILE="/tmp/asr_test_$$.mp3"
echo "fake audio content" > "$FAKE_FILE"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -X POST "$URL" \
    -F "file=@${FAKE_FILE};filename=test.mp3")

if [ "$HTTP_CODE" = "400" ]; then
    pass "服务正确拒绝非 WAV 文件（HTTP 400）"
else
    fail "期望 HTTP 400，实际收到 HTTP ${HTTP_CODE}"
fi
rm -f "$FAKE_FILE"
echo ""

# ──────────────────────────────────────────────
# 汇总结果
# ──────────────────────────────────────────────
echo "=========================================="
echo -e "  测试结果：${GREEN}通过 ${PASS}${NC} 项 / ${RED}失败 ${FAIL}${NC} 项"
echo "=========================================="
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}  所有测试通过，ASR Service 运行正常！${NC}"
    exit 0
else
    echo -e "${RED}  存在失败项，请检查服务日志${NC}"
    exit 1
fi
