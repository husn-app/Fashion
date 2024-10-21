
from flask import Flask, jsonify, render_template, redirect, request, url_for, make_response, session, g
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import torch
torch.set_grad_enabled(False)

import pyodbc
# Disable pyodb pooling, to let sqlalchemy use it's own pooling.
# Reference: https://docs.sqlalchemy.org/en/20/dialects/mssql.html#pyodbc-pooling-connection-close-behavior
pyodbc.pooling = False

from authlib.integrations.flask_client import OAuth
from config import Config
from models import User, WishlistItem, UserClick
from flask_migrate import Migrate
import random
import datetime
import google_auth_handler

app = Flask(__name__)
app.config.from_object(Config)  

# Import db after disabling pyodbc pooling.
from db import db
db.init_app(app)
migrate = Migrate(app, db)
print(f"using {app.config['DEPLOYMENT_TYPE']=}\n{app.config['DATABASE_TYPE']=}")


# Register cookie handlers.
import cookie_handler
app.before_request(cookie_handler.get_auth_info)
app.after_request(cookie_handler.update_cookies)


# Define after db, because it uses db.session for writes.
import core ## Loads all artifacts as well. 

oauth = OAuth(app)
google_oauth = google_auth_handler.get_google_oauth(oauth)

ONBOARDING_COMPLETE = 'COMPLETE'
MAN, WOMAN = 'MAN', 'WOMAN'


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
    if g.user_id and request.cookies.get('onboarding_stage') != ONBOARDING_COMPLETE:
        return redirect('/onboarding')

    if not g.user_id:
        session['login_message'] = "Login to see your personalized feed!"
        return redirect('/login-screen')

    feed_products = core.get_feed(g.user_id)
    return render_template('feed.html', feed_products=feed_products)

@app.route('/login-screen')
def login_screen():
    login_message = session.pop('login_message', None)
    return render_template('login_screen.html', login_message=login_message)

@app.route('/')
def home():
    if g.user_id and request.cookies.get('onboarding_stage') != ONBOARDING_COMPLETE:
        return redirect('/onboarding')
    
    if not g.user_id:
        return redirect('/inspiration')
    
    return redirect('/feed')

@app.route('/inspiration', defaults={'gender': None})
@app.route('/inspiration/<path:gender>')
def inspirations(gender):
    user_gender = request.cookies.get('gender')
    if g.user_id and user_gender in (MAN, WOMAN):
        gender = user_gender

    gender = gender or WOMAN
    gender = gender.upper()
    if gender not in (MAN, WOMAN):
        return redirect('/inspiration')
    return render_template('inspirations.html', inspirations=core.get_inspirations(gender), gender=gender.lower())

@app.route('/onboarding', methods = ['GET', 'POST'])
def onboarding():
    if not g.user_id:
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
            user = User.query.get(g.user_id)
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
    user_id = g.user_id if g.user_id else None
    product = core.get_product(product_id, user_id=user_id)
    if not product:
        return redirect('/')

    if g.user_id:
        user_click = UserClick(user_id=g.user_id, product_index=product_id)
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
    user_id = g.user_id if g.user_id else None
    try:
        return {'products' : core.get_similar_products(product_id),
                'is_wishlisted' : core.is_wishlisted(product_id=product_id, user_id=user_id)
                }
    except Exception as e:
        return jsonify({"error": e}), 400
        
# Route for login
@app.route('/login')
def login():
    if g.user_id:
        return redirect('/')
    session['next_url'] = request.referrer or '/'
    redirect_uri = url_for('authorize', _external=True)
    print(f"{redirect_uri=}")
    return google_oauth.authorize_redirect(redirect_uri)

# Route for authorization callback
@app.route('/authorize')
def authorize():
    if g.user_id:
        return redirect("/")
    next_url = session.pop('next_url', '/')
    
    user_info = google_auth_handler.get_user_info(google_oauth)
    if not user_info:
        return redirect(next_url)
    
    user = core.create_user_if_needed(user_info)
    if not user:
        return redirect(next_url)
        
    cookie_handler.set_cookie_updates_at_login(user=user)
    return redirect(next_url)

# Route for logout
@app.route('/logout')
def logout():
    response = make_response(redirect('/'))
    return cookie_handler.get_logged_out_response(response)


@app.route('/wishlist/<int:index>', methods=['POST'])
def toggle_wishlist_product(index):
    if not g.user_id:
        return '', 401
    # wishlist_item = WishlistItem(user_id=g.user_id, product_index=index)
    wishlist_item = WishlistItem.query.filter_by(user_id=g.user_id, product_index=index).first()
    if wishlist_item:
        # Item exists, so remove it from the wishlist
        db.session.delete(wishlist_item)
        db.session.commit()
        print("Item removed from wishlist.")
        return jsonify({"is_wishlisted": False}), 200
        # Item does not exist, so add it to the wishlist
    new_item = WishlistItem(user_id=g.user_id, product_index=index)
    db.session.add(new_item)
    db.session.commit()
    print("Item added to wishlist.")
    return jsonify({"is_wishlisted": True}), 200

@app.route('/wishlist')
def wishlist():
    if not g.user_id:
        session['login_message'] = "Login to see your wishlist!"
        return redirect('/login-screen')

    wishlisted_products = db.session.query(WishlistItem.product_index).filter_by(user_id=g.user_id).all()
    wishlisted_indices = [index[0] for index in wishlisted_products if index[0] < len(products_df)]
    products = products_df.iloc[wishlisted_indices].to_dict('records')
    return render_template('wishlist.html', products=products)

if __name__ == '__main__':
    app.run(debug=True)
