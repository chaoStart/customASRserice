import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from asr_model import ASRService
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
# 下面这个导包不要删除！！！
from funasr.models.fun_asr_nano.model import FunASRNano
# ──────────────────────────────────────────────
# 环境变量配置
#   ASR_POOL_SIZE      : 同时运行的模型实例数（默认 2）
#                        CPU 推理可适当增大；单 GPU 建议保持 1~2
#   ASR_MAX_WAIT       : 等待空闲模型的最长秒数（默认 60）
# ──────────────────────────────────────────────
POOL_SIZE = int(os.getenv("ASR_POOL_SIZE", "1"))
MAX_WAIT = float(os.getenv("ASR_MAX_WAIT", "60.0"))

current_dir = os.path.dirname(os.path.abspath(__file__))
model_local_path = os.path.join(current_dir, "models", "FunAudioLLM", "Fun-ASR-Nano-2512")
print("当前运行文件的路径:", current_dir)
print("模型的存储路径：", type(model_local_path), model_local_path)
print(f"模型池大小: {POOL_SIZE}")


# ──────────────────────────────────────────────
# 模型池
# ──────────────────────────────────────────────
class ASRModelPool:
    """
    管理多个 ASRService 实例的异步池。

    工作流程：
      1. 启动时创建 POOL_SIZE 个模型实例，放入 asyncio.Queue。
      2. 每次推理请求：从队列取出一个实例 → 在 ThreadPoolExecutor
         中执行阻塞推理（不阻塞事件循环）→ 推理完成后归还实例。
      3. 队列为空时，新请求等待；超过 MAX_WAIT 秒则返回 503。
    """

    def __init__(self, model_path: str, pool_size: int):
        self._model_path = model_path
        self._pool_size = pool_size
        self._queue: asyncio.Queue | None = None
        # 线程池大小与模型池相同，保证每个模型实例最多占用一个线程
        self._executor = ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="asr-worker")

    async def initialize(self):
        """在事件循环启动后调用，逐个加载模型实例。"""
        self._queue = asyncio.Queue(maxsize=self._pool_size)
        for i in range(self._pool_size):
            print(f"正在加载模型实例 {i + 1}/{self._pool_size} ...")
            model = ASRService(self._model_path)
            await self._queue.put(model)
        print("全部模型实例加载完成，服务就绪。")

    async def transcribe(self, wav_path: str) -> str:
        """
        从池中取模型 → 线程池推理 → 归还模型。
        若等待超时则抛出 503。
        """
        try:
            model: ASRService = await asyncio.wait_for(
                self._queue.get(), timeout=MAX_WAIT
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503,
                detail=f"服务繁忙，在 {MAX_WAIT:.0f}s 内没有可用模型实例，请稍后重试"
            )

        try:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(
                self._executor,
                model.convert_wav_text,
                wav_path,
            )
            return text
        finally:
            # 无论成功或异常，都归还实例
            await self._queue.put(model)

    def shutdown(self):
        self._executor.shutdown(wait=False)

# ──────────────────────────────────────────────
# 应用生命周期
# ──────────────────────────────────────────────
asr_pool = ASRModelPool(model_local_path, POOL_SIZE)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asr_pool.initialize()
    yield
    asr_pool.shutdown()


app = FastAPI(lifespan=lifespan)

# ──────────────────────────────────────────────
# 接口
# ──────────────────────────────────────────────
@app.post("/asr/wav_to_text_binary")
async def wav_to_text_binary(file: UploadFile = File(...)):
    if not file.filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="仅支持 wav 文件")

    # 将上传内容写入临时文件（异步读取，不阻塞事件循环）
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
        tmp.write(await file.read())

    print("音频文件的路径：", wav_path)
    try:
        text = await asr_pool.transcribe(wav_path)
        return {"success": True, "text": text}
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
