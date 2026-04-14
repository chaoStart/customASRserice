import requests
import time
import concurrent.futures
import os

# ================= 配置区域 =================
# 接口地址 (保持 8000)
API_URL = "http://localhost:8000/v1/chat/completions"

# 获取当前工作目录
current_dir = os.getcwd()
print(f"当前工作目录: {current_dir}")

# 本地文件路径
LOCAL_FILE_PATH = os.path.join(current_dir, "weather_nice_slow.wav")

# 执行这个脚本需要在命令行中执行python -m http.server 1234将当前本地音频文件修改为在线可访问音频文件
# 对应上面的 python -m http.server 1234
# 我们将本地路径转换为 http 地址
FILE_NAME = os.path.basename(LOCAL_FILE_PATH)
AUDIO_URL = f"http://localhost:1234/{FILE_NAME}"

CONCURRENT_COUNT = 100


# ===========================================

def send_single_request(task_id):
    """
    单个请求的执行函数
    """
    result = {
        "id": task_id,
        "duration": 0.0,
        "status": "未知",
        "message": ""
    }

    start_time = time.time()

    try:
        headers = {"Content-Type": "application/json"}

        # 构造 JSON 请求
        # 这里使用上面生成的 http://localhost:1234/... 链接
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "audio_url",
                            "audio_url": {
                                "url": AUDIO_URL
                            },
                        }
                    ],
                }
            ]
        }

        # 发送请求
        response = requests.post(API_URL, headers=headers, json=data, timeout=60)

        end_time = time.time()
        duration = end_time - start_time
        result["duration"] = duration

        if response.status_code == 200:
            result["status"] = "成功"
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            result["message"] = f"内容: {content[:200]}..."
        else:
            result["status"] = "失败"
            result["message"] = f"状态码: {response.status_code} - {response.text[:50]}"

    except Exception as e:
        result["status"] = "异常"
        result["message"] = str(e)

    return result


def run_concurrent_test():
    print(f"🚀 开始并发测试: {CONCURRENT_COUNT} 个并发请求...")
    print(f"目标地址: {API_URL}")
    print(f"音频地址: {AUDIO_URL}")  # 打印确认音频地址
    print("-" * 50)

    overall_start = time.time()
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_COUNT) as executor:
        futures = [executor.submit(send_single_request, i) for i in range(CONCURRENT_COUNT)]

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            all_results.append(result)
            status_icon = "✅" if result["status"] == "成功" else "❌"
            print(
                f"{status_icon} 任务 {result['id']}: {result['status']} (耗时: {result['duration']:.2f}s) - {result['message']}")

    overall_end = time.time()

    # ================= 统计计算 =================
    successful_durations = [r["duration"] for r in all_results if r["status"] == "成功"]

    print("-" * 50)
    print(f"🏁 所有测试完成。")
    print(f"⏱️  总耗时: {overall_end - overall_start:.2f}秒")

    if successful_durations:
        avg_duration = sum(successful_durations) / len(successful_durations)
        max_duration = max(successful_durations)
        min_duration = min(successful_durations)

        print(f"📊 成功请求数: {len(successful_durations)}/{CONCURRENT_COUNT}")
        print(f"📈 平均耗时: {avg_duration:.2f}秒")
        print(f"🔺 最大耗时: {max_duration:.2f}秒")
        print(f"🔻 最小耗时: {min_duration:.2f}秒")
    else:
        print("⚠️  没有成功的请求，无法计算平均耗时。")


if __name__ == "__main__":
    run_concurrent_test()