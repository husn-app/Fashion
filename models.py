from db import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, index=True)  # Internal ID for your app
    auth_id = db.Column(db.String(255), unique=True, nullable=False)  # 'sub' field (Google's unique user ID)
    email = db.Column(db.String(255), index=True, unique=True, nullable=False)  # 'email' field
    name = db.Column(db.String(255), nullable=True)  # 'name' field
    given_name = db.Column(db.String(255), nullable=True)  # 'given_name' field
    family_name = db.Column(db.String(255), nullable=True)  # 'family_name' field
    picture_url = db.Column(db.String(255), nullable=True)  # 'picture' field (URL to profile picture)
    refresh_token = db.Column(db.String(512), nullable=True)
    wishlisted_products = db.relationship('WishlistItem', backref='user')

class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Add a primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    product_index = db.Column(db.Integer, index=True)
