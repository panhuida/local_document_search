from sqlalchemy import (Column, Integer, String, Text, TIMESTAMP, BigInteger, Index)
from sqlalchemy.sql import func
from app.extensions import db
from sqlalchemy.dialects import postgresql

class Document(db.Model):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    file_name = Column(String(200), nullable=False)
    file_type = Column(String(50))
    file_size = Column(BigInteger)
    file_created_at = Column(TIMESTAMP)
    file_modified_time = Column(TIMESTAMP)
    file_path = Column(Text, nullable=False, unique=True)
    markdown_content = Column(Text)
    is_converted = Column(Integer)  # 0-直接存储，1-文本转Markdown，2-代码转Markdown，3-结构化转Markdown，4-转换失败
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_documents_file_path', 'file_path', unique=True),
        # Note: PGroonga indexes are created manually via SQL in the migration
        # and are not explicitly defined in the model's __table_args__.
    )

class ConversionError(db.Model):
    __tablename__ = 'conversion_errors'

    id = Column(Integer, primary_key=True)
    file_name = Column(String(200), nullable=False)
    file_path = Column(Text, nullable=False)
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

