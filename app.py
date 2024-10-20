
from flask import Flask, jsonify, render_template, redirect, request, url_for, make_response, session
import time

import torch
torch.set_grad_enabled(False)

import pyodbc
# Disable pyodb pooling, to let sqlalchemy use it's own pooling.
# Reference: https://docs.sqlalchemy.org/en/20/dialects/mssql.html#pyodbc-pooling-connection-close-behavior
pyodbc.pooling = False

from authlib.integrations.flask_client import OAuth
from config import Config
from flask_login import LoginManager, login_user, current_user, login_required, logout_user
from models import User, WishlistItem, UserClick
from flask_migrate import Migrate
import random
import datetime

import random


app = Flask(__name__)
app.config.from_object(Config)  

# Import db after disabling pyodbc pooling.
from db import db
db.init_app(app)
migrate = Migrate(app, db)
print(f"using {app.config['DEPLOYMENT_TYPE']=}\n{app.config['DATABASE_TYPE']=}")

import core


assert app.config['GOOGLE_CLIENT_ID'] is not None
assert app.config['GOOGLE_CLIENT_SECRET'] is not None
# Initialize LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

ONBOARDING_COMPLETE = 'COMPLETE'
MAN, WOMAN = 'MAN', 'WOMAN'

@login_manager.user_loader
def load_user(id):
    try:
        return User.query.get(int(id))
    except ValueError:
        return None
    except Exception as ex:
        print(f"Couldnt load user:{ex}")


oauth = OAuth(app)
google = oauth.register(
    name='google',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={
        'scope': 'openid email profile', # https://www.googleapis.com/auth/user.birthday.read https://www.googleapis.com/auth/user.gender.read',
    },
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    include_granted_scopes=True
)

@app.template_filter('shuffle')
def filter_shuffle(seq):
    try:
        result = list(seq)
        random.shuffle(result)
        return result
    except:
        return seq


@app.context_processor
def inject_deployment_type():
    return dict(deployment_type=app.config['DEPLOYMENT_TYPE'])

@app.route('/feed')
def feed_route():
    if current_user.is_authenticated and current_user.onboarding_stage != ONBOARDING_COMPLETE:
        return redirect('/onboarding')

    if not current_user.is_authenticated:
        session['login_message'] = "Login to see your personalized feed!"
        return redirect('/login-screen')

    feed_products = core.get_feed(current_user.id)
    return render_template('feed.html', feed_products=feed_products)

@app.route('/login-screen')
def login_screen():
    login_message = session.pop('login_message', None)
    return render_template('login_screen.html', login_message=login_message)

@app.route('/')
def home():
    if current_user.is_authenticated and current_user.onboarding_stage != ONBOARDING_COMPLETE:
        return redirect('/onboarding')
    
    if not current_user.is_authenticated:
        return redirect('/inspiration')
    
    return redirect('/feed')

@app.route('/inspiration', defaults={'gender': None})
@app.route('/inspiration/<path:gender>')
def inspirations(gender):
    if current_user.is_authenticated and current_user.gender in (MAN, WOMAN):
        gender = current_user.gender.lower()
    gender = gender or 'woman'
    if gender not in ('man', 'woman'):
        return redirect('/inspiration')
    return render_template('inspirations.html', inspirations=core.get_inspirations(gender), gender=gender)

@app.route('/onboarding', methods = ['GET', 'POST'])
def onboarding():
    if not current_user.is_authenticated:
        return redirect('/login')
    if request.method == 'GET':
        return render_template('onboarding.html')
    
    if request.method == 'POST':
        # Process form data here
        form_data = request.form
        gender = str(request.form.get('gender', ''))
        age = 0
        try:
            age = int(request.form.get('age', 0))
        except:
            pass
            
        if gender not in (MAN, WOMAN) and (age < 12 or age > 72):
            print('ATTENTION: Someone manually edited the onboarding form. Form data : ', request.form)
            return redirect('/onboarding')
        
        try:
            user = User.query.get(current_user.id)
            user.gender = gender
            user.birth_year = datetime.datetime.now().year - age
            user.onboarding_stage = ONBOARDING_COMPLETE
            
            db.session.commit()
        except Exception as e:
            print('Error commiting onboarding data to db: ', e)
            return redirect('/onboarding')
        
        # Redirect to home or another page after processing
        return redirect('/')

# Path captures anything that comes after /query. So any other routes like /query/some-route/<> won't work. 
@app.route('/query/<path:query>')
def web_query(query):
    # Frontend slugifies the urls by converting spaces to ' '. 
    query = query.replace('-', ' ')
    return render_template('query.html', products=core.get_search_results(query))

@app.route('/api/query')
def api_query():
    try:
        data = request.json
        query = data.get('query')
        return jsonify({'products' : core.process_query(query)})
    except Exception as e:
        return jsonify({'error' : e})


@app.route('/product/<string:slug>/<int:product_id>')
def web_product(slug, product_id):
    user_id = current_user.id if current_user.is_authenticated else None
    product = core.get_product(product_id, user_id=user_id)
    if not product:
        return redirect('/')

    if current_user.is_authenticated:
        user_click = UserClick(user_id=current_user.id, product_index=product_id)
        db.session.add(user_click)
        # TODO: Make this asynchronous. We don't care if we lose some of the clicks. 
        db.session.commit()
        
    # TODO: Use is_wishlisted as part of the product itself. 
    return render_template('product.html', current_product=product, products=core.get_similar_products(product_id), is_wishlisted=product['is_wishlisted'])

# TODO: Figure out how the flow works for product main page. 
# 1. We pass the product from the previous state, so openeing of a product is instant, and load similar products later. How to retrieve wishlist?
# 2. We fetch both current product and previous products.
@app.route('/api/similar_products/<int:product_id>')
def api_similar_products(product_id):
    user_id = current_user.id if current_user.is_authenticated else None
    try:
        return {'products' : core.get_similar_products(product_id),
                'is_wishlisted' : core.is_wishlisted(product_id=product_id, user_id=user_id)
                }
    except Exception as e:
        return jsonify({"error": e}), 400
        
# Route for login
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect('/')
    session['next_url'] = request.referrer or '/'
    redirect_uri = url_for('authorize', _external=True)
    if 'http://' in redirect_uri and '127.0.0.1' not in redirect_uri:
        redirect_uri = redirect_uri.replace('http://', 'https://')
    print(f"{redirect_uri=}")
    return google.authorize_redirect(redirect_uri)

# Route for authorization callback
@app.route('/authorize')
def authorize():
    if current_user.is_authenticated:
        return redirect('/')
    try:
        _ = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()
        print(f"Google-Authorize:{user_info=}")
        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            user = User(auth_id=user_info.get('id'), email=user_info.get('email'), name=user_info.get('name'),
                        given_name=user_info.get('given_name'), family_name=user_info.get('family_name'),
                        picture_url=user_info.get('picture'))
            db.session.add(user)
            print(f"Created {user=}")

        db.session.commit()

        login_user(user)
    except Exception as ex:
        print(f"Couldn't login user:{ex}")

    next_url = session.pop('next_url', '/')
    return redirect(next_url)

# Route for logout
@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')


@app.route('/wishlist/<int:index>', methods=['POST'])
@login_required
def toggle_wishlist_product(index):
    # wishlist_item = WishlistItem(user_id=current_user.id, product_index=index)
    wishlist_item = WishlistItem.query.filter_by(user_id=current_user.id, product_index=index).first()
    if wishlist_item:
        # Item exists, so remove it from the wishlist
        db.session.delete(wishlist_item)
        db.session.commit()
        print("Item removed from wishlist.")
        return jsonify({"is_wishlisted": False}), 200
        # Item does not exist, so add it to the wishlist
    new_item = WishlistItem(user_id=current_user.id, product_index=index)
    db.session.add(new_item)
    db.session.commit()
    print("Item added to wishlist.")
    return jsonify({"is_wishlisted": True}), 200

@app.route('/wishlist')
def wishlist():
    if not current_user.is_authenticated:
        session['login_message'] = "Login to see your wishlist!"
        return redirect('/login-screen')

    wishlisted_products = db.session.query(WishlistItem.product_index).filter_by(user_id=current_user.id).all()
    wishlisted_indices = [index[0] for index in wishlisted_products if index[0] < len(products_df)]
    products = products_df.iloc[wishlisted_indices].to_dict('records')
    return render_template('wishlist.html', products=products)

if __name__ == '__main__':
    app.run(debug=True)
