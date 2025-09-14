import os
from datetime import datetime, timezone
import traceback
from flask import current_app
from markitdown import MarkItDown
from app.utils.file_utils import get_file_metadata
from app.models import Document, ConversionType, IngestState
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

# Initialize markitdown instance
_md = MarkItDown()

def _convert_to_markdown(file_path, file_type):
    """
    Converts a file to Markdown format with fine-grained error handling.
    Returns a tuple of (content, conversion_type).
    On failure, returns (error_message, None).
    """
    file_type_lower = file_type.lower()
    
    try:
        if file_type_lower in current_app.config.get('NATIVE_MARKDOWN_TYPES', []):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                conversion_type = ConversionType.DIRECT
            except (IOError, OSError) as e:
                return f"Error reading native markdown file: {e}", None

        elif file_type_lower in current_app.config.get('PLAIN_TEXT_TO_MARKDOWN_TYPES', []):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                content = f"# {os.path.basename(file_path)}\n\n{text}"
                conversion_type = ConversionType.TEXT_TO_MD
            except (IOError, OSError) as e:
                return f"Error reading plain text file: {e}", None

        elif file_type_lower in current_app.config.get('CODE_TO_MARKDOWN_TYPES', []):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                content = f"# {os.path.basename(file_path)}\n\n```{file_type_lower}\n{text}\n```"
                conversion_type = ConversionType.CODE_TO_MD
            except (IOError, OSError) as e:
                return f"Error reading code file: {e}", None

        elif file_type_lower in current_app.config.get('STRUCTURED_TO_MARKDOWN_TYPES', []):
            try:
                with open(file_path, 'rb') as f:
                    result = _md.convert(f)
                if not result.text_content or not result.text_content.strip():
                    return f"Markitdown conversion resulted in empty content for {file_path}", None
                content = result.text_content
                conversion_type = ConversionType.STRUCTURED_TO_MD
            except Exception as e:
                return f"Markitdown conversion failed: {e}", None
        else:
            return f"Unsupported file type: {file_type}", None

        sanitized_content = content.replace('\x00', '')
        return sanitized_content, conversion_type
        
    except Exception as e:
        error_message = f"An unexpected error occurred in converter for {file_path}: {e}\n{traceback.format_exc()}"
        return error_message, None

def ingest_folder(folder_path, date_from_str, date_to_str, recursive, file_types_str):
    """
    Orchestrates the entire ingestion process for a folder, integrates with IngestState,
    and yields progress updates.
    """
    logger = current_app.logger
    start_time = datetime.now(timezone.utc)

    # --- IngestState Management ---
    ingest_state = db.session.query(IngestState).filter_by(source='local_fs', scope_key=folder_path).first()
    if not ingest_state:
        ingest_state = IngestState(source='local_fs', scope_key=folder_path)
        db.session.add(ingest_state)
    
    ingest_state.last_started_at = start_time
    ingest_state.last_error_message = None
    db.session.commit()

    # Use cursor if date_from is not specified, to allow for overrides
    cursor_time = ingest_state.cursor_updated_at if not date_from_str else None

    processed_files, skipped_files, error_files = 0, 0, 0

    try:
        # --- Timezone-aware date parsing ---
        date_from, date_to = None, None
        try:
            if date_from_str:
                date_from = datetime.fromisoformat(date_from_str).replace(tzinfo=timezone.utc)
            elif cursor_time:
                # Use cursor if no start date is provided
                date_from = cursor_time

            if date_to_str:
                date_to = datetime.fromisoformat(date_to_str + 'T23:59:59.999999').replace(tzinfo=timezone.utc)
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}")

        # --- File type parsing ---
        file_types = [ft.strip().lower() for ft in file_types_str.split(',')] if file_types_str else None

        yield {'level': 'info', 'message': f"Starting folder scan: {folder_path}", 'stage': 'scan_start'}
        
        # --- Unified File Scanning & Filtering ---
        matched_files = []
        logger.debug(f"os.walk starting with folder_path: '{folder_path}'")
        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if not d.endswith('.assets')]
            
            for file in files:
                logger.debug(f"  - Found root: '{root}', file: '{file}'")
                file_path = os.path.join(root, file)
                
                if file_types and not file.lower().endswith(tuple(f".{ft}" for ft in file_types)):
                    continue

                metadata = get_file_metadata(file_path)
                if not metadata:
                    continue

                file_modified_time_utc = metadata['file_modified_time']
                if date_from and file_modified_time_utc < date_from:
                    continue
                if date_to and file_modified_time_utc > date_to:
                    continue
                
                matched_files.append(file_path)

            if not recursive:
                break
        
        total_files = len(matched_files)
        ingest_state.total_files = total_files
        db.session.commit()
        yield {'level': 'info', 'message': f"Scan found {total_files} matching files.", 'stage': 'scan_complete', 'total_files': total_files}

        if total_files == 0:
            summary = {'total_files': 0, 'processed_files': 0, 'skipped_files': 0, 'error_files': 0}
            yield {'level': 'info', 'message': "No files to process.", 'stage': 'done', 'summary': summary}
            # Even if no files, we mark this as a successful run
            ingest_state.cursor_updated_at = start_time
            return

        for i, file_path in enumerate(matched_files):
            progress = int(((i + 1) / total_files) * 100)
            yield {'level': 'info', 'message': f"Processing file {i+1}/{total_files}: {os.path.basename(file_path)}", 'stage': 'file_processing', 'progress': progress, 'current_file': os.path.basename(file_path)}

            metadata = get_file_metadata(file_path)
            if not metadata:
                yield {'level': 'warning', 'message': f"Could not get metadata for {file_path}, skipping.", 'stage': 'file_skip'}
                continue

            existing_doc = Document.query.filter(Document.file_path.ilike(metadata['file_path'])).first()
            if existing_doc and existing_doc.file_modified_time == metadata['file_modified_time']:
                skipped_files += 1
                yield {'level': 'info', 'message': f"Skipping unchanged file: {file_path}", 'stage': 'file_skip', 'reason': 'unchanged'}
                continue

            content, conversion_type = _convert_to_markdown(file_path, metadata['file_type'])

            if conversion_type is None:
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
                        status='failed', error_message=error_message, source='local_fs'
                    )
                    db.session.add(new_doc)
                yield {'level': 'error', 'message': f"Failed to convert file: {file_path}. Reason: {error_message}", 'stage': 'file_error'}
            else:
                if existing_doc:
                    existing_doc.file_size = metadata['file_size']
                    existing_doc.file_modified_time = metadata['file_modified_time']
                    existing_doc.markdown_content = content
                    existing_doc.conversion_type = conversion_type
                    existing_doc.status = 'completed'
                    existing_doc.error_message = None
                else:
                    new_doc = Document(
                        file_name=metadata['file_name'], file_type=metadata['file_type'],
                        file_size=metadata['file_size'], file_created_at=metadata['file_created_at'],
                        file_modified_time=metadata['file_modified_time'], file_path=metadata['file_path'],
                        markdown_content=content, conversion_type=conversion_type, status='completed', source='local_fs'
                    )
                    db.session.add(new_doc)
                processed_files += 1
                yield {'level': 'info', 'message': f"Successfully processed: {file_path}", 'stage': 'file_success'}
            
            # Commit per file to save progress incrementally
            db.session.commit()

        # On successful completion, update the cursor
        ingest_state.cursor_updated_at = start_time

        summary = {'total_files': total_files, 'processed_files': processed_files, 'skipped_files': skipped_files, 'error_files': error_files}
        yield {'level': 'info', 'message': "All files processed.", 'stage': 'done', 'summary': summary}

    except Exception as e:
        error_msg = f"A critical error occurred: {e}\n{traceback.format_exc()}"
        logger.critical(error_msg)
        ingest_state.last_error_message = error_msg
        yield {'level': 'critical', 'message': f"A critical error occurred: {str(e)}", 'stage': 'critical_error'}
    finally:
        # This block will run whether there was an error or not
        ingest_state.processed = processed_files
        ingest_state.skipped = skipped_files
        ingest_state.errors = error_files
        ingest_state.last_ended_at = datetime.now(timezone.utc)
        db.session.commit()
