
import threading
import torch
from funasr import AutoModel
from funasr.models.fun_asr_nano.model import FunASRNano
class ASRService:
    def __init__(self, model_local_path):
        self.model_dir = "FunAudioLLM/Fun-ASR-Nano-2512"
        self._lock = threading.Lock()  # 保证单实例线程安全
        self.device = (
            "cuda:0"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )

        print("ASR device:", self.device)

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
        if hotwords is None:
            hotwords = ["天气"]
        with self._lock:  # 防止同一实例被并发调用
            res = self.model.generate(
                input=[wav_path],
                cache={},
                batch_size=batch_size,
                hotwords=hotwords,
                language=language,
                itn=True,
            )
        return res[0]["text"]
