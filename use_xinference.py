# pip install "xinference[vllm]",版本是2.4.0
from xinference.client import Client

client = Client("http://localhost:9997")
# 启动语音模型
# model_uid = client.launch_model(model_name="Fun-ASR-Nano-2512", model_type="audio")
# print("model_uid:",model_uid)
# 手动选择想要使用语音模型（也可以通过nacos读取）
model = client.get_model('Fun-ASR-Nano-2512')

# input_text = "an apple"
with open("/mnt/workspace/weather_nice_slow.wav", "rb") as audio_file:
    results = model.transcriptions(audio_file.read())
    # 打印语音识别后的结果
    print(results)