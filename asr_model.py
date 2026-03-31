import os
import threading
import torch
from typing import List
from funasr import AutoModel
from funasr.models.fun_asr_nano.model import FunASRNano


class ASRService:
    def __init__(self, model_local_path):
        self.model_dir = "FunAudioLLM/Fun-ASR-Nano-2512"
        self._lock = threading.Lock()
        
        cuda_env = os.getenv("CUDA_DEVICE_INDEX", "0")
        if cuda_env == "cpu" or not torch.cuda.is_available():
            if torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = f"cuda:{int(cuda_env)}"

        print("ASR device:", self.device)

        cuda_mem_fraction = os.environ.get("CUDA_MEMORY_FRACTION")
        if cuda_mem_fraction:
            fraction = float(cuda_mem_fraction)
            if torch.cuda.is_available() and 0 < fraction <= 1.0:
                torch.cuda.set_per_process_memory_fraction(fraction)
            print(f"GPU 显存利用率上限:{fraction * 100:.0f}%")

        self.model = AutoModel(
            model=self.model_dir,
            model_path=model_local_path,
            trust_remote_code=False,
            remote_code="./model.py",
            disable_update=True,
            device=self.device,
            hub="ms",
        )

    def convert_wav_text(self, wav_path: str, batch_size=1, hotwords=None, language="中文") -> str:
        """单文件推理（兼容旧接口）"""
        if hotwords is None:
            hotwords = ["开放时间"]
        with self._lock:
            res = self.model.generate(
                input=[wav_path],
                cache={},
                batch_size=batch_size,
                hotwords=hotwords,
                language=language,
                itn=True,
            )
        return res[0]["text"]

    def convert_wav_text_batch(self, wav_paths: List[str], hotwords=None, language="中文") -> List[str]:
        """
        批处理多个音频文件，提升 GPU 利用率
        返回：每个音频的识别结果列表
        """
        if hotwords is None:
            hotwords = ["开放时间"]
        
        with self._lock:
            res = self.model.generate(
                input=wav_paths,
                cache={},
                batch_size=len(wav_paths),
                hotwords=hotwords,
                language=language,
                itn=True,
            )
        
        return [item["text"] for item in res]
