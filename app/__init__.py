import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from flask import Flask, g, request
from config import Config
from app.extensions import db, migrate
from app.i18n import supported_lang, t
from app.routes import convert, search, main, cleanup, wechat


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)

    @app.before_request
    def _detect_lang():
        """Language resolution order:
        1. Explicit query parameter `?lang=` if supported
        2. Cookie 'lang' if supported
        3. Accept-Language header (first matching zh / en)
        4. Fallback: zh
        """
        # 1. Query parameter override
        param_lang = request.args.get('lang')
        if param_lang and supported_lang(param_lang):
            g.lang = param_lang
            return

        # 2. Cookie
        cookie_lang = request.cookies.get('lang')
        if cookie_lang and supported_lang(cookie_lang):
            g.lang = cookie_lang
            return

        # 3. Accept-Language header simple parse (no full q-value weighting needed for zh/en)
        header = request.headers.get('Accept-Language', '')
        selected = None
        if header:
            # Split on commas, take order priority; inspect language-range before optional ;q=
            for part in header.split(','):
                lang_range = part.split(';', 1)[0].strip().lower()
                if lang_range.startswith('zh'):
                    selected = 'zh'
                    break
                if lang_range.startswith('en'):
                    selected = 'en'
                    break
        g.lang = selected if selected else 'zh'

    @app.after_request
    def _persist_lang(resp):
        # Ensure a cookie is set so subsequent navigations need not re-parse Accept-Language
        current = getattr(g, 'lang', 'zh')
        existing = request.cookies.get('lang')
        if current and current != existing:
            resp.set_cookie('lang', current, max_age=60*60*24*365, path='/')
        return resp

    @app.context_processor
    def _inject_i18n():
        current = getattr(g, 'lang', 'zh')
        return {
            't': t,
            'current_lang': current,
        }

    # 注册蓝图
    app.register_blueprint(main.bp)
    app.register_blueprint(convert.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(cleanup.cleanup_bp)
    app.register_blueprint(wechat.wechat_bp)

    # 设置日志
    setup_logging(app)

    app.logger.info('Application startup')

    return app

def setup_logging(app):
    # Forcefully remove all existing handlers to avoid duplicates
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
        
    log_level_str = app.config.get('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    app.logger.setLevel(log_level)

    # Create a stream handler for console output (only in development)
    time_fmt = app.config.get('LOG_TIME_FORMAT', '%Y-%m-%d %H:%M:%S')
    if app.debug or os.environ.get('FLASK_ENV') == 'development':
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt=time_fmt))
        app.logger.addHandler(stream_handler)

    # File handler - Timed Rotating
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        file_handler = TimedRotatingFileHandler(
            filename=os.path.join('logs', 'app.log'),
            when='midnight',
            interval=1,
            backupCount=app.config.get('LOG_BACKUP_COUNT'),
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt=time_fmt))
        file_handler.setLevel(log_level)
        app.logger.addHandler(file_handler)

        # Error file handler
        error_handler = logging.FileHandler(
            os.path.join('logs', 'errors.log'),
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt=time_fmt))
        app.logger.addHandler(error_handler)
