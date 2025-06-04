import secrets
import logging
from functools import wraps
from flask import request, jsonify, g
from flask_sqlalchemy import SQLAlchemy


class UserAuth:
    def __init__(self, app=None, admin_key=None, logger=None):
        self.db = SQLAlchemy()
        self.admin_key = admin_key
        self.logger = logger

        if app:
            self.init_app(app)

    def init_app(self, app):
        self.db.init_app(app)

        # sqlalchemy model for API clients
        class APIClient(self.db.Model):
            id = self.db.Column(self.db.Integer, primary_key=True)
            name = self.db.Column(self.db.String(100), nullable=False)
            email = self.db.Column(self.db.String(120), nullable=False)
            api_key = self.db.Column(self.db.String(64), unique=True, nullable=False)

            def __repr__(self):
                return f'<APIClient {self.name}>'

            def to_dict(self):
                return {
                    'id': self.id,
                    'name': self.name,
                    'email': self.email,
                    'api_key': self.api_key
                }

        self.APIClient = APIClient

    def error_response(self, message, status_code=400):
        return jsonify({'error': message}), status_code

    def validate_admin(self, f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header or not auth_header.startswith('Bearer '):
                self.logger.error(f"Missing admin key")
                return self.error_response('Invalid admin key', 401)
            api_key = auth_header[7:]
            if not api_key or api_key != self.admin_key:
                self.logger.warning(f"Invalid admin key")
                return self.error_response('Invalid admin key', 401)

            self.logger.info(f"Admin access granted")
            return f(*args, **kwargs)

        return decorated_function

    def validate_api(self, f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header or not auth_header.startswith('Bearer '):
                self.logger.error(f"Invalid user key")
                return self.error_response('Invalid user key', 401)
            api_key = auth_header[7:]
            if not api_key:
                return self.error_response('Invalid user key', 401)

            # Check if admin key
            if api_key == self.admin_key:
                self.logger.info(f"Admin access via API endpoint from {request.remote_addr}")
                return f(*args, **kwargs)

            # Find client
            client = self.APIClient.query.filter_by(api_key=api_key).first()
            if not client:
                self.logger.error(f"Invalid user key")
                return self.error_response('Invalid user key', 401)

            self.logger.info(f"API access granted")
            return f(*args, **kwargs)

        return decorated_function

    def create_client(self, name, email):
        if self.APIClient.query.filter_by(email=email).first():
            raise ValueError('Email already exists')

        client = self.APIClient(
            name=name,
            email=email,
            api_key=secrets.token_urlsafe(32)
        )

        self.db.session.add(client)
        self.db.session.commit()

        self.logger.info(f"Created new client: {name} ({email})")
        return client