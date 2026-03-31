"""
ASR 服务并发测试脚本
测试 10 个并发请求的性能表现
"""
import asyncio
import aiohttp
import time
import os
import sys

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────
SERVER_URL = "http://localhost:8000/asr/wav_to_text_binary"
CONCURRENT_REQUESTS = 10  # 并发请求数
TEST_WAV_PATH = r"D:\github_code\customASRserice\weather_nice_male.wav"  # 测试音频路径


async def send_request(session: aiohttp.ClientSession, request_id: int) -> dict:
    """发送单个 ASR 请求"""
    start_time = time.time()
    
    try:
        # 检查测试文件是否存在
        if not os.path.exists(TEST_WAV_PATH):
            return {
                "request_id": request_id,
                "status": "error",
                "error": f"测试文件不存在：{TEST_WAV_PATH}",
                "duration": 0
            }
        
        # 读取音频文件
        with open(TEST_WAV_PATH, "rb") as f:
            wav_data = f.read()
        
        # 构建 multipart/form-data 请求（FastAPI UploadFile 格式）
        form_data = aiohttp.FormData()
        form_data.add_field(
            "file",
            wav_data,
            filename="weather_nice_male.wav",
            content_type="audio/wav"
        )
        
        # 发送请求
        async with session.post(
            SERVER_URL,
            data=form_data,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as response:
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status == 200:
                result = await response.json()
                return {
                    "request_id": request_id,
                    "status": "success",
                    "text": result.get("text", "")[:50] + "..." if len(result.get("text", "")) > 50 else result.get("text", ""),
                    "duration": duration,
                    "http_status": response.status
                }
            else:
                error_text = await response.text()
                return {
                    "request_id": request_id,
                    "status": "error",
                    "error": error_text,
                    "duration": duration,
                    "http_status": response.status
                }
    
    except asyncio.TimeoutError:
        return {
            "request_id": request_id,
            "status": "timeout",
            "error": "请求超时 (120s)",
            "duration": time.time() - start_time
        }
    except Exception as e:
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "duration": time.time() - start_time
        }


async def run_concurrent_test():
    """运行并发测试"""
    print("=" * 60)
    print("🚀 ASR 服务并发测试")
    print("=" * 60)
    print(f"服务器地址：{SERVER_URL}")
    print(f"并发请求数：{CONCURRENT_REQUESTS}")
    print(f"测试音频：{TEST_WAV_PATH}")
    print("=" * 60)
    
    # 检查测试文件
    if not os.path.exists(TEST_WAV_PATH):
        print(f"\n❌ 错误：测试文件不存在：{TEST_WAV_PATH}")
        print("\n💡 提示：请确认文件路径是否正确")
        return
    
    # 获取文件大小
    file_size_mb = os.path.getsize(TEST_WAV_PATH) / (1024 * 1024)
    print(f"测试文件大小：{file_size_mb:.2f} MB")
    print("=" * 60)
    print(f"\n⏳ 开始发送 {CONCURRENT_REQUESTS} 个并发请求...\n")
    
    start_total = time.time()
    
    async with aiohttp.ClientSession() as session:
        # 并发发送所有请求
        tasks = [send_request(session, i + 1) for i in range(CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)
    
    end_total = time.time()
    total_duration = end_total - start_total
    
    # 分析结果
    print("\n" + "=" * 60)
    print("📊 测试结果")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    timeout_count = sum(1 for r in results if r["status"] == "timeout")
    
    print(f"\n✅ 成功：{success_count}/{CONCURRENT_REQUESTS}")
    print(f"❌ 失败：{error_count}/{CONCURRENT_REQUESTS}")
    print(f"⏰ 超时：{timeout_count}/{CONCURRENT_REQUESTS}")
    
    if success_count > 0:
        durations = [r["duration"] for r in results if r["status"] == "success"]
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        print(f"\n⏱️  响应时间统计 (仅成功请求):")
        print(f"   平均：{avg_duration:.2f} 秒")
        print(f"   最短：{min_duration:.2f} 秒")
        print(f"   最长：{max_duration:.2f} 秒")
        print(f"   总耗时：{total_duration:.2f} 秒")
        
        # 计算吞吐量
        throughput = success_count / total_duration
        print(f"\n📈 吞吐量：{throughput:.2f} 请求/秒")
        
        # 详细结果
        print(f"\n📋 详细结果:")
        print("-" * 60)
        for r in results:
            status_emoji = "✅" if r["status"] == "success" else "❌" if r["status"] == "error" else "⏰"
            print(f"{status_emoji} 请求 {r['request_id']:2d}: {r['duration']:.2f}s - ", end="")
            if r["status"] == "success":
                print(f"识别结果：{r['text']}")
            else:
                print(f"错误：{r['error'][:50]}...")
    
    print("\n" + "=" * 60)
    
    # 性能评估
    print("\n💡 性能评估:")
    if success_count == CONCURRENT_REQUESTS:
        if total_duration < CONCURRENT_REQUESTS * 0.5:
            print("   🎉 优秀！批处理效果显著，并发性能良好")
        elif total_duration < CONCURRENT_REQUESTS * 0.8:
            print("   👍 良好！批处理正常工作")
        else:
            print("   ⚠️  一般！批处理可能未生效，建议检查服务配置")
    else:
        print("   ⚠️  部分请求失败，请检查服务状态")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(run_concurrent_test())
