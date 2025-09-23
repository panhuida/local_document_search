from faster_whisper import WhisperModel

# 选择模型大小：tiny, base, small, medium, large-v1, large-v2, large-v3
model_size = "tiny"

# 初始化模型
model = WhisperModel(model_size, device="cpu", compute_type="int8")
# 如果没有GPU，使用: device="cpu", compute_type="int8"

# 转录音频文件
segments, info = model.transcribe("E:\\videos\\强烈推荐！凯文·凯利揭示AI时代三大变革趋势.mp4")

print("检测到的语言 '%s' 概率 %f" % (info.language, info.language_probability))

for segment in segments:
    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))