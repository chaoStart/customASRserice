1、创建和激活虚拟环境
conda create -n asrservice python=3.10 -y

2、根据requirements.txt文件进行安装依赖
pip install -r requirements.txt文件进行安装依赖

3、执行download_model.py文件下面语音模型
python download_model.py

4、下载完模型之后执行启动ASR服务，进行音频文件识别
python app.py