from .db import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)  # Internal ID for your app
    auth_id = db.Column(db.String(255), unique=True, nullable=False)  # 'sub' field (Google's unique user ID)
    email = db.Column(db.String(255), index=True, unique=True, nullable=False)  # 'email' field
    name = db.Column(db.String(255), nullable=True)  # 'name' field
    given_name = db.Column(db.String(255), nullable=True)  # 'given_name' field
    family_name = db.Column(db.String(255), nullable=True)  # 'family_name' field
    picture_url = db.Column(db.String(255), nullable=True)  # 'picture' field (URL to profile picture)
    issued_at = db.Column(db.Integer, nullable=True)  # 'iat' field (when the token was issued)
    # expires_at = db.Column(db.Integer, nullable=True)
    # access_token = db.Column(db.String)
    refresh_token = db.Column(db.String(500), nullable=True)