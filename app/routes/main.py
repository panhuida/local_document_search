from flask import Blueprint, render_template, request
from app.models import ConversionError

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('search.html')

@bp.route('/process')
def convert_page():
    return render_template('convert.html')

@bp.route('/search')
def search_page():
    return render_template('search.html')

@bp.route('/errors')
def errors_page():
    query = ConversionError.query

    # Search by filename
    file_name_search = request.args.get('file_name', '')
    if file_name_search:
        query = query.filter(ConversionError.file_name.ilike(f'%{file_name_search}%'))

    # Filter by date
    date_from = request.args.get('date_from', '')
    if date_from:
        query = query.filter(ConversionError.updated_at >= date_from)
    
    date_to = request.args.get('date_to', '')
    if date_to:
        query = query.filter(ConversionError.updated_at <= date_to)

    # Sort by updated_at
    query = query.order_by(ConversionError.updated_at.desc())

    errors = query.all()

    return render_template('errors.html', errors=errors, file_name_search=file_name_search, date_from=date_from, date_to=date_to)