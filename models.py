from .db import db
from flask_login import UserMixin

wishlist_table = db.Table('wishlist',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True)
)

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

    wishlisted_products = db.relationship('Product', secondary=wishlist_table, backref='users')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.Integer, nullable=False)
    landingPageUrl = db.Column(db.String(255), nullable=True)
    productId = db.Column(db.String(255), unique=True, nullable=False, index=True)
    product = db.Column(db.String(255), nullable=False)
    productName = db.Column(db.String(255), nullable=False)
    rating = db.Column(db.Float, nullable=True)
    ratingCount = db.Column(db.Integer, nullable=True)
    brand = db.Column(db.String(255), nullable=True)
    searchImage = db.Column(db.String(255), nullable=True)
    sizes = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(50), nullable=True)
    primaryColour = db.Column(db.String(50), nullable=True)
    additionalInfo = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(255), nullable=True)
    price = db.Column(db.Float, nullable=False)
    articleType = db.Column(db.String(255), nullable=True)
    subCategory = db.Column(db.String(255), nullable=True)
    masterCategory = db.Column(db.String(255), nullable=True)

