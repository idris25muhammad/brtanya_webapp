# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
socketio = SocketIO()
login_manager = LoginManager()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    migrate.init_app(app, db)
    
    # Setup Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes.admin import admin_bp
    from app.routes.participant import participant_bp
    from app.routes.auth import auth_bp
    
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(participant_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Register SocketIO events
    from app.sockets import events
    
    return app
