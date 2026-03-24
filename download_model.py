import os
from modelscope import snapshot_download

# 获取当前脚本所在目录（asr_model.py 所在路径）
current_dir = os.path.dirname(os.path.abspath(__file__))
print("当前运行文件的路径", current_dir)
download_models = os.path.join(current_dir, "models")

# 下载语音模型
snapshot_download('FunAudioLLM/Fun-ASR-Nano-2512', cache_dir=download_models, max_workers=1)