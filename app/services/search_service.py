import re
from app.models import Document
from app.extensions import db
from sqlalchemy import func, cast, TEXT, literal_column

def search_documents(keyword, search_type='full_text', sort_by='relevance', sort_order='desc', page=1, per_page=20, file_types=None, date_from=None, date_to=None):
    """搜索文档"""
    query = Document.query

    if file_types:
        query = query.filter(Document.file_type.in_(file_types))

    if date_from:
        query = query.filter(Document.file_modified_time >= date_from)
    if date_to:
        query = query.filter(Document.file_modified_time <= date_to)

    if keyword:
        if search_type == 'full_text':
            # Directly inject the SQL for pgroonga_score to avoid argument errors
            score_col = literal_column("pgroonga_score(documents)").label("score")
            query = query.with_entities(Document, score_col)
            query = query.filter(
                db.or_(
                    Document.file_name.op('&@')(keyword),
                    Document.markdown_content.op('&@')(keyword)
                )
            )
        
        elif search_type == 'trigram':
            # Calculate similarity score against content and filename
            similarity_score = func.greatest(
                func.similarity(Document.markdown_content, keyword),
                func.similarity(Document.file_name, keyword)
            ).label("similarity")
            
            # Add the score to the query's selectable entities
            query = query.with_entities(Document, similarity_score)

    # --- UNIFIED AND RESTRUCTURED SORTING LOGIC ---
    order_by_clause = None

    # 1. Handle relevance sort first
    if keyword and sort_by == 'relevance':
        if search_type == 'full_text':
            # For PGroonga, we order by the calculated score
            order_by_clause = db.desc("score")
        elif search_type == 'trigram':
            # For trigram, we order by the calculated similarity score
            order_by_clause = db.desc("similarity")

    # 2. If relevance sort was not applicable, handle other sort options
    if order_by_clause is None:
        if sort_by == 'filename':
            order_by_clause = Document.file_name.desc() if sort_order == 'desc' else Document.file_name.asc()
        elif sort_by == 'mtime':
            order_by_clause = Document.file_modified_time.desc() if sort_order == 'desc' else Document.file_modified_time.asc()
        else:
            # 3. Final fallback to default sort order
            order_by_clause = Document.file_modified_time.desc()

    query = query.order_by(order_by_clause)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return pagination