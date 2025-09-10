import re
from app.models import Document
from app.extensions import db
from sqlalchemy import func, cast, TEXT

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
            processed_keyword = ' & '.join(re.split(r'[\s+]+', keyword))
            query = query.filter(Document.search_vector.match(processed_keyword, postgresql_regconfig='simple'))
        
        elif search_type == 'trigram':
            query = query.filter(
                db.or_(
                    Document.markdown_content.op('%>')(keyword),
                    Document.file_name.op('%>')(keyword)
                )
            )

    # --- UNIFIED AND RESTRUCTURED SORTING LOGIC ---
    order_by_clause = None

    # 1. Handle relevance sort first
    if keyword and sort_by == 'relevance':
        if search_type == 'full_text':
            processed_keyword = ' & '.join(re.split(r'[\s+]+', keyword))
            order_by_clause = func.ts_rank(Document.search_vector, func.to_tsquery('simple', processed_keyword)).desc()
        elif search_type == 'trigram':
            # Fallback for Trigram relevance sort is modification time to ensure an indexable ORDER BY
            order_by_clause = Document.file_modified_time.desc() if sort_order == 'desc' else Document.file_modified_time.asc()

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