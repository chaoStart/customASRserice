import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from asr_model import ASRService
from typing import List
from dataclasses import dataclass
import time
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
# 下面这个导包不要删除！！！
from funasr.models.fun_asr_nano.model import FunASRNano

# ──────────────────────────────────────────────
# 环境变量配置
#   ASR_POOL_SIZE      : 模型实例数（单 GPU 建议保持 1）
#   ASR_MAX_WAIT       : 等待空闲模型的最长秒数（默认 60）
#   ASR_BATCH_SIZE     : 批处理大小（默认 4）
#   ASR_BATCH_TIMEOUT  : 批处理等待超时时间（秒，默认 0.5）
# ──────────────────────────────────────────────
POOL_SIZE = int(os.getenv("ASR_POOL_SIZE", "1"))
MAX_WAIT = float(os.getenv("ASR_MAX_WAIT", "60.0"))
BATCH_SIZE = int(os.getenv("ASR_BATCH_SIZE", "4"))
BATCH_TIMEOUT = float(os.getenv("ASR_BATCH_TIMEOUT", "0.5"))

current_dir = os.path.dirname(os.path.abspath(__file__))
model_local_path = os.path.join(current_dir, "models", "FunAudioLLM", "Fun-ASR-Nano-2512")
print("当前运行文件的路径:", current_dir)
print("模型的存储路径：", type(model_local_path), model_local_path)
print(f"模型池大小：{POOL_SIZE}, 批处理大小：{BATCH_SIZE}")


# ──────────────────────────────────────────────
# 批处理请求队列
# ──────────────────────────────────────────────
@dataclass
class PendingRequest:
    wav_path: str
    future: asyncio.Future
    timestamp: float


class BatchProcessor:
    """
    将多个 ASR 请求聚合成 batch，一次性推理，提升 GPU 利用率
    """
    def __init__(self, model: ASRService, batch_size: int, batch_timeout: float):
        self.model = model
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.queue: asyncio.Queue[PendingRequest] = asyncio.Queue()
        self._processor_task: asyncio.Task | None = None

    async def start(self):
        """启动批处理后台任务"""
        self._processor_task = asyncio.create_task(self._process_batches())

    async def stop(self):
        """停止批处理任务"""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

    async def submit(self, wav_path: str) -> str:
        """提交一个推理请求，返回 Future"""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        request = PendingRequest(wav_path=wav_path, future=future, timestamp=time.time())
        await self.queue.put(request)
        return await future

    async def _process_batches(self):
        """后台任务：不断从队列收集请求，组成 batch 后推理"""
        while True:
            try:
                # 收集第一批请求
                first_request = await self.queue.get()
                batch: List[PendingRequest] = [first_request]

                # 继续收集，直到达到 batch_size 或超时
                try:
                    while len(batch) < self.batch_size:
                        remaining_time = self.batch_timeout - (time.time() - first_request.timestamp)
                        if remaining_time <= 0:
                            break
                        try:
                            request = await asyncio.wait_for(
                                self.queue.get(),
                                timeout=remaining_time
                            )
                            batch.append(request)
                        except asyncio.TimeoutError:
                            break
                except Exception as e:
                    # 收集过程中的异常，处理已收集的请求
                    pass

                # 执行批处理推理
                await self._run_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"批处理异常：{e}")
                await asyncio.sleep(0.1)

    async def _run_batch(self, batch: List[PendingRequest]):
        """执行一批推理请求"""
        wav_paths = [req.wav_path for req in batch]
        
        try:
            loop = asyncio.get_running_loop()
            # 在线程池中执行批处理推理
            results = await loop.run_in_executor(
                None,
                lambda: self.model.convert_wav_text_batch(wav_paths)
            )

            # 将结果分发给各个请求
            for req, result in zip(batch, results):
                if not req.future.done():
                    req.future.set_result(result)

        except Exception as e:
            # 异常时通知所有请求
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)


# ──────────────────────────────────────────────
# 模型池（简化为单实例 + 批处理）
# ──────────────────────────────────────────────
class ASRModelPool:
    def __init__(self, model_path: str, pool_size: int, batch_size: int, batch_timeout: float):
        self._model_path = model_path
        self._pool_size = pool_size
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._model: ASRService | None = None
        self._batch_processor: BatchProcessor | None = None

    async def initialize(self):
        print(f"正在加载模型实例 (单 GPU 优化模式)...")
        self._model = ASRService(self._model_path)
        self._batch_processor = BatchProcessor(
            self._model,
            self._batch_size,
            self._batch_timeout
        )
        await self._batch_processor.start()
        print("模型加载完成，批处理服务就绪。")

    async def transcribe(self, wav_path: str) -> str:
        """通过批处理器提交请求"""
        return await self._batch_processor.submit(wav_path)

    async def shutdown(self):
        if self._batch_processor:
            await self._batch_processor.stop()


# ──────────────────────────────────────────────
# 应用生命周期
# ──────────────────────────────────────────────
asr_pool = ASRModelPool(model_local_path, POOL_SIZE, BATCH_SIZE, BATCH_TIMEOUT)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asr_pool.initialize()
    yield
    await asr_pool.shutdown()


app = FastAPI(lifespan=lifespan)

# ──────────────────────────────────────────────
# 接口
# ──────────────────────────────────────────────
@app.post("/asr/wav_to_text_binary")
async def wav_to_text_binary(file: UploadFile = File(...)):
    if not file.filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="仅支持 wav 文件")

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
