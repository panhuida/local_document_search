from app.models import Document
from app.extensions import db
from sqlalchemy import func

def search_documents(keyword, search_type='simple', sort_by='relevance', sort_order='desc', page=1, per_page=20, file_types=None, date_from=None, date_to=None):
    """搜索文档"""
    query = Document.query

    if keyword:
        query = query.filter(Document.markdown_content.ilike(f'%{keyword}%'))

    if file_types:
        query = query.filter(Document.file_type.in_(file_types))

    if date_from:
        query = query.filter(Document.file_modified_time >= date_from)
    if date_to:
        query = query.filter(Document.file_modified_time <= date_to)

    if sort_by == 'filename':
        order = Document.file_name.desc() if sort_order == 'desc' else Document.file_name.asc()
        query = query.order_by(order)
    else:
        order = Document.file_modified_time.desc() if sort_order == 'desc' else Document.file_modified_time.asc()
        query = query.order_by(order)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return pagination