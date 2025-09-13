import os
import time
import json
import tkinter as tk
from tkinter import filedialog
from flask import Blueprint, request, jsonify, current_app, Response
from app.services.file_scanner import scan_folder
from app.services.converter import convert_to_markdown
from app.utils.file_utils import get_file_metadata
from app.models import Document
from app.extensions import db
from sqlalchemy import func

bp = Blueprint('convert', __name__, url_prefix='/api')

@bp.route('/browse-folder', methods=['GET'])
def browse_folder():
    """
    Opens a dialog for the user to select a folder.
    Returns the selected folder path.
    """
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main tkinter window
        root.attributes('-topmost', True)
        folder_path = filedialog.askdirectory(master=root)
        return jsonify({'status': 'success', 'folder_path': folder_path})
    except Exception as e:
        current_app.logger.error(f"Error opening folder dialog: {e}")
        return jsonify({'status': 'error', 'message': 'Could not open folder dialog.'}), 500

def generate_conversion_stream(app, folder_path, date_from, date_to, recursive, file_types):
    """
    A generator function that scans and converts files, yielding progress updates.
    This function runs within a Flask application context.
    """
    with app.app_context():
        logger = current_app.logger
        
        def stream_log(message, level='info', **kwargs):
            log_data = {'level': level, 'message': message, **kwargs}
            yield f"data: {json.dumps(log_data)}\n\n"

        try:
            yield from stream_log(f"Starting folder scan: {folder_path}", 'info', stage='scan_start')
            
            matched_files = scan_folder(folder_path, date_from, date_to, recursive, file_types)
            total_files = len(matched_files)
            
            yield from stream_log(f"Scan found {total_files} matching files.", 'info', stage='scan_complete', total_files=total_files)

            if total_files == 0:
                summary = {'total_files': 0, 'processed_files': 0, 'skipped_files': 0, 'error_files': 0}
                yield from stream_log("No files to process.", 'info', stage='done', summary=summary)
                return

            processed_files = 0
            skipped_files = 0
            error_files = 0

            for i, file_path in enumerate(matched_files):
                progress = int(((i + 1) / total_files) * 100)
                yield from stream_log(f"Processing file {i+1}/{total_files}: {os.path.basename(file_path)}", 'info', stage='file_processing', progress=progress, current_file=os.path.basename(file_path))

                metadata = get_file_metadata(file_path)
                if not metadata:
                    yield from stream_log(f"Could not get metadata for {file_path}, skipping.", 'warning', stage='file_skip')
                    continue

                existing_doc = Document.query.filter_by(file_path=metadata['file_path']).first()
                if existing_doc and existing_doc.file_modified_time == metadata['file_modified_time']:
                    skipped_files += 1
                    yield from stream_log(f"Skipping unchanged file: {file_path}", 'info', stage='file_skip', reason='unchanged')
                    continue

                markdown_content, is_converted = convert_to_markdown(file_path, metadata['file_type'])

                if is_converted == 4:
                    error_files += 1
                    error_message = markdown_content
                    if existing_doc:
                        existing_doc.status = 'failed'
                        existing_doc.error_message = error_message
                    else:
                        # Even if conversion fails, we create a record to track it.
                        new_doc = Document(
                            file_name=metadata['file_name'],
                            file_type=metadata['file_type'],
                            file_size=metadata['file_size'],
                            file_created_at=metadata['file_created_at'],
                            file_modified_time=metadata['file_modified_time'],
                            file_path=metadata['file_path'],
                            content=None,
                            conversion_type=is_converted,
                            status='failed',
                            error_message=error_message
                        )
                        db.session.add(new_doc)
                    yield from stream_log(f"Failed to convert file: {file_path}. Reason: {error_message}", 'error', stage='file_error')
                    continue

                if existing_doc:
                    existing_doc.file_size = metadata['file_size']
                    existing_doc.file_modified_time = metadata['file_modified_time']
                    existing_doc.content = markdown_content
                    existing_doc.conversion_type = is_converted
                    existing_doc.status = 'completed'
                    existing_doc.error_message = None # Clear previous errors
                else:
                    new_doc = Document(
                        file_name=metadata['file_name'],
                        file_type=metadata['file_type'],
                        file_size=metadata['file_size'],
                        file_created_at=metadata['file_created_at'],
                        file_modified_time=metadata['file_modified_time'],
                        file_path=metadata['file_path'],
                        content=markdown_content,
                        conversion_type=is_converted,
                        status='completed'
                    )
                    db.session.add(new_doc)
                
                db.session.commit() # Commit after each file operation
                processed_files += 1
                yield from stream_log(f"Successfully processed: {file_path}", 'info', stage='file_success')

            # The final commit is no longer needed here as we commit after each file.
            
            summary = {
                'total_files': total_files,
                'processed_files': processed_files,
                'skipped_files': skipped_files,
                'error_files': error_files
            }
            yield from stream_log("All files processed.", 'info', stage='done', summary=summary)

        except Exception as e:
            logger.error(f"An error occurred during conversion stream: {e}", exc_info=True)
            yield from stream_log(f"A critical error occurred: {str(e)}", 'critical', stage='critical_error')


@bp.route('/convert-stream')
def convert_stream_route():
    folder_path = request.args.get('folder_path')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    recursive = request.args.get('recursive', 'true').lower() == 'true'
    file_types = request.args.get('file_types')

    if not folder_path or not os.path.isdir(folder_path):
        def error_stream():
            error_data = {'level': 'critical', 'message': 'Invalid or missing folder path.', 'stage': 'critical_error'}
            yield f"data: {json.dumps(error_data)}\n\n"
        return Response(error_stream(), mimetype='text/event-stream')
    
    app = current_app._get_current_object()
    return Response(generate_conversion_stream(app, folder_path, date_from, date_to, recursive, file_types), mimetype='text/event-stream')

@bp.route('/retry-conversion/<int:doc_id>', methods=['POST'])
def retry_conversion(doc_id):
    """
    Retries the conversion for a document that previously failed.
    """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'status': 'error', 'message': 'Document not found.'}), 404

    if doc.status != 'failed':
        return jsonify({'status': 'error', 'message': 'Document is not in a failed state.'}), 400

    try:
        # Reset status to 'pending' to be picked up by a background processor
        # or directly trigger the conversion again.
        # For simplicity, we'll directly convert it here.
        
        markdown_content, conversion_type = convert_to_markdown(doc.file_path, doc.file_type)

        if conversion_type == 4: # Conversion failed again
            doc.error_message = markdown_content
            db.session.commit()
            return jsonify({'status': 'error', 'message': f'Retry failed: {markdown_content}'})
        
        # Conversion succeeded
        doc.content = markdown_content
        doc.conversion_type = conversion_type
        doc.status = 'completed'
        doc.error_message = None
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Document successfully reconverted.'})

    except Exception as e:
        current_app.logger.error(f"Error retrying conversion for doc {doc_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred during retry.'}), 500

