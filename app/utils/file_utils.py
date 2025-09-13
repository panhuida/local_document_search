import os
import unicodedata
from datetime import datetime, timezone
from flask import current_app

def get_file_metadata(file_path):
    """获取文件元数据"""
    try:
        # 首先，使用原始路径获取文件状态，避免因路径处理导致找不到文件
        stat = os.stat(file_path)

        # 规范化路径以存入数据库：NFC Unicode, 使用 / 分隔符, 保持盘符原始大小写
        # 注意：os.path.abspath 在这里是关键，因为它会返回一个大小写正确的盘符
        abs_path = os.path.abspath(file_path)
        nfc_path = unicodedata.normalize('NFC', abs_path)
        final_path = nfc_path.replace('\\', '/')

        return {
            'file_name': os.path.basename(file_path),
            'file_type': os.path.splitext(file_path)[1].lstrip('.'),
            'file_size': stat.st_size,
            'file_created_at': datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
            'file_modified_time': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            'file_path': final_path
        }
    except FileNotFoundError:
        current_app.logger.warning(f"File not found when trying to get metadata: {file_path}")
        return None
