import os
import datetime
import traceback
from flask import current_app
from markitdown import MarkItDown
from app.utils.file_utils import get_file_metadata
from app.models import Document
from app.extensions import db

# Initialize markitdown instance
_md = MarkItDown()

def _scan_folder(folder_path, date_from=None, date_to=None, recursive=True, file_types=None):
    """
    Scans a folder and filters files based on given criteria.
    (Moved from file_scanner.py)
    """
    matched_files = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.endswith('.assets')]
        for file in files:
            if file_types and not file.lower().endswith(tuple(file_types)):
                continue

            file_path = os.path.join(root, file)
            try:
                modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if date_from and modified_time < date_from:
                    continue
                if date_to and modified_time > date_to:
                    continue
                matched_files.append(file_path)
            except FileNotFoundError:
                continue
        if not recursive:
            break
    return matched_files

def _convert_to_markdown(file_path, file_type):
    """
    Converts a file to Markdown format.
    (Moved from converter.py)
    """
    try:
        file_type_lower = file_type.lower()
        content = ""
        conversion_type = 4  # Default to error/unsupported

        if file_type_lower in current_app.config.get('NATIVE_MARKDOWN_TYPES', []):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            conversion_type = 0
        elif file_type_lower in current_app.config.get('PLAIN_TEXT_TO_MARKDOWN_TYPES', []):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
                content = f"# {os.path.basename(file_path)}\n\n{text}"
            conversion_type = 1
        elif file_type_lower in current_app.config.get('CODE_TO_MARKDOWN_TYPES', []):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
                content = f"# {os.path.basename(file_path)}\n\n```{file_type_lower}\n{text}\n```"
            conversion_type = 2
        elif file_type_lower in current_app.config.get('STRUCTURED_TO_MARKDOWN_TYPES', []):
            with open(file_path, 'rb') as f:
                result = _md.convert(f)
            if not result.text_content or not result.text_content.strip():
                return f"Conversion resulted in empty content for {file_path}", 4
            content = result.text_content
            conversion_type = 3
        else:
            return f"Unsupported file type: {file_type}", 4

        sanitized_content = content.replace('\x00', '')
        return sanitized_content, conversion_type
    except Exception as e:
        error_message = f"Converter failed for {file_path}: {e}\n{traceback.format_exc()}"
        return error_message, 4

def ingest_folder(folder_path, date_from, date_to, recursive, file_types):
    """
    Orchestrates the entire ingestion process for a folder and yields progress updates.
    (Core logic from routes/convert.py)
    """
    logger = current_app.logger
    try:
        yield {'level': 'info', 'message': f"Starting folder scan: {folder_path}", 'stage': 'scan_start'}
        
        matched_files = _scan_folder(folder_path, date_from, date_to, recursive, file_types)
        total_files = len(matched_files)
        
        yield {'level': 'info', 'message': f"Scan found {total_files} matching files.", 'stage': 'scan_complete', 'total_files': total_files}

        if total_files == 0:
            summary = {'total_files': 0, 'processed_files': 0, 'skipped_files': 0, 'error_files': 0}
            yield {'level': 'info', 'message': "No files to process.", 'stage': 'done', 'summary': summary}
            return

        processed_files, skipped_files, error_files = 0, 0, 0

        for i, file_path in enumerate(matched_files):
            progress = int(((i + 1) / total_files) * 100)
            yield {'level': 'info', 'message': f"Processing file {i+1}/{total_files}: {os.path.basename(file_path)}", 'stage': 'file_processing', 'progress': progress, 'current_file': os.path.basename(file_path)}

            metadata = get_file_metadata(file_path)
            if not metadata:
                yield {'level': 'warning', 'message': f"Could not get metadata for {file_path}, skipping.", 'stage': 'file_skip'}
                continue

            existing_doc = Document.query.filter_by(file_path=metadata['file_path']).first()
            if existing_doc and existing_doc.file_modified_time == metadata['file_modified_time']:
                skipped_files += 1
                yield {'level': 'info', 'message': f"Skipping unchanged file: {file_path}", 'stage': 'file_skip', 'reason': 'unchanged'}
                continue

            content, conversion_type = _convert_to_markdown(file_path, metadata['file_type'])

            if conversion_type == 4:
                error_files += 1
                error_message = content
                if existing_doc:
                    existing_doc.status = 'failed'
                    existing_doc.error_message = error_message
                else:
                    new_doc = Document(
                        file_name=metadata['file_name'], file_type=metadata['file_type'],
                        file_size=metadata['file_size'], file_created_at=metadata['file_created_at'],
                        file_modified_time=metadata['file_modified_time'], file_path=metadata['file_path'],
                        status='failed', error_message=error_message
                    )
                    db.session.add(new_doc)
                yield {'level': 'error', 'message': f"Failed to convert file: {file_path}. Reason: {error_message}", 'stage': 'file_error'}
            else:
                if existing_doc:
                    existing_doc.file_size = metadata['file_size']
                    existing_doc.file_modified_time = metadata['file_modified_time']
                    existing_doc.content = content
                    existing_doc.conversion_type = conversion_type
                    existing_doc.status = 'completed'
                    existing_doc.error_message = None
                else:
                    new_doc = Document(
                        file_name=metadata['file_name'], file_type=metadata['file_type'],
                        file_size=metadata['file_size'], file_created_at=metadata['file_created_at'],
                        file_modified_time=metadata['file_modified_time'], file_path=metadata['file_path'],
                        content=content, conversion_type=conversion_type, status='completed'
                    )
                    db.session.add(new_doc)
                processed_files += 1
                yield {'level': 'info', 'message': f"Successfully processed: {file_path}", 'stage': 'file_success'}
            
            db.session.commit()

        summary = {'total_files': total_files, 'processed_files': processed_files, 'skipped_files': skipped_files, 'error_files': error_files}
        yield {'level': 'info', 'message': "All files processed.", 'stage': 'done', 'summary': summary}

    except Exception as e:
        logger.error(f"An error occurred during ingestion: {e}", exc_info=True)
        yield {'level': 'critical', 'message': f"A critical error occurred: {str(e)}", 'stage': 'critical_error'}
