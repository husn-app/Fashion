from db import db
from flask_login import UserMixin
from datetime import datetime
import pytz

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, index=True)  # Internal ID for your app
    auth_id = db.Column(db.String(255), nullable=True)  # 'sub' field (Google's unique user ID)
    email = db.Column(db.String(255), index=True, unique=True, nullable=False)  # 'email' field
    name = db.Column(db.String(255), nullable=True)  # 'name' field
    given_name = db.Column(db.String(255), nullable=True)  # 'given_name' field
    family_name = db.Column(db.String(255), nullable=True)  # 'family_name' field
    picture_url = db.Column(db.String(255), nullable=True)  # 'picture' field (URL to profile picture)
    refresh_token = db.Column(db.String(512), nullable=True)
    gender = db.Column(db.Enum('MAN', 'WOMAN', name='gender_enum'), nullable=True)
    birth_year = db.Column(db.Integer, nullable=True)
    onboarding_stage = db.Column(db.Enum('PENDING', 'COMPLETE', name='onboarding_stage_enum'), nullable=True)
    wishlisted_products = db.relationship('WishlistItem', backref='user')
    created_at = db.Column(db.DateTime, nullable=True, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    
    # Apple sign-in specific fields. 
    sub = db.Column(db.String(255), nullable=True, index=True)
    is_private_email = db.Column(db.Boolean, default=False)

    def __repr__(self) -> str:
        return f"{self.id=}\n{self.email=}\n{self.name=}"

class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Add a primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    product_index = db.Column(db.Integer, index=True)
    referrer = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, nullable=True, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    
class UserClick(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Add a primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True, nullable=True)
    session_id = db.Column(db.String, nullable=True)
    product_index = db.Column(db.Integer, nullable=True)
    search_query = db.Column(db.String, nullable=True)
    referrer = db.Column(db.String, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)