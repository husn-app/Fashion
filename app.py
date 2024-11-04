
from flask import Flask, jsonify, render_template, redirect, request, url_for, make_response, session, g, abort, send_from_directory

import torch
torch.set_grad_enabled(False)

import pyodbc
# Disable pyodb pooling, to let sqlalchemy use it's own pooling.
# Reference: https://docs.sqlalchemy.org/en/20/dialects/mssql.html#pyodbc-pooling-connection-close-behavior
pyodbc.pooling = False

from authlib.integrations.flask_client import OAuth
from config import Config
from models import User
from flask_migrate import Migrate
import random
import google_auth_handler
from google.oauth2 import id_token
from google.auth.transport import requests as google_api_requests
import apple_auth_handler

app = Flask(__name__)
app.config.from_object(Config) 

for key in ['DEPLOYMENT_TYPE', 'DATABASE_TYPE', 'POOL_PRE_PING', 'LOGGING_DESTINATION', 'SCRAPING_BOTS']:
    print(f"{key} : {app.config[key]}") 

# Import db after disabling pyodbc pooling.
from db import db
db.init_app(app)
migrate = Migrate(app, db)

import db_logging

# Register cookie handlers.
import cookie_handler
app.before_request(cookie_handler.get_auth_info)
app.after_request(cookie_handler.update_cookies)


# Define after db, because it uses db.session for writes.
import core ## Loads all artifacts as well. 

oauth = OAuth(app)
google_oauth = google_auth_handler.get_google_oauth(oauth)

@app.context_processor
def inject_deployment_type():
    return dict(deployment_type=app.config['DEPLOYMENT_TYPE'])

# ============================= #
# Static Routes                 #
# ============================= #
@app.route('/robots.txt')
def robots_txt():
    if Config.DEPLOYMENT_TYPE == 'PROD':
        return app.send_static_file('robots.txt')
    return app.send_static_file('robots-dev.txt')

@app.route('/privacypolicy')
def privacypolicy():
    return render_template('privacypolicy.html')

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/.well-known/assetlinks.json')
def well_known():
    return send_from_directory('static', 'assetlinks.json')

@app.route('/login-screen')
def login_screen():
    return render_template('login_screen.html')

@app.route('/')
def home():
    if g.user_id and request.cookies.get('onboarding_stage') != core.ONBOARDING_COMPLETE:
        return redirect('/onboarding')
    
    if not g.user_id:
        return redirect('/inspiration')
    
    return redirect('/feed')

# ============================= #
# Feed                          #
# ============================= #
@app.route('/feed')
def web_feed():
    if g.user_id and request.cookies.get('onboarding_stage') != core.ONBOARDING_COMPLETE:
        return redirect('/onboarding')

    if not g.user_id:
        return redirect('/login-screen')

    feed_products = core.get_feed(g.user_id)
    return render_template('feed.html', feed_products=feed_products)

@app.route('/api/feed', methods=['GET', 'POST'])
def api_feed():
    return jsonify({'products' : core.get_feed(g.user_id)})

# ============================= #
# Inspirations                  #
# ============================= #
@app.route('/inspiration', defaults={'gender': None})
@app.route('/inspiration/<path:gender>')
def web_inspirations(gender):
    inspirations, gender = core.get_inspirations(gender=gender)
    return render_template('inspirations.html', inspirations=inspirations, gender=gender)

@app.route('/api/inspiration', defaults={'gender': None}, methods = ['GET', 'POST'])
@app.route('/api/inspiration/<path:gender>', methods=['GET', 'POST'])
def api_inspirations(gender):
    inspirations, gender = core.get_inspirations(gender=gender)
    return jsonify({'inspirations' : inspirations})

# ============================= #
# Search                        #
# ============================= #
# Path captures anything that comes after /query. So any other routes like /query/some-route/<> won't work. 
@app.route('/query/<path:query>')
def web_query(query):
    # Frontend slugifies the urls by converting spaces to ' '. 
    query = query.replace('-', ' ')
    db_logging.log_search(query, request.referrer)
    return render_template('query.html', products=core.get_search_results(query), query=query)

@app.route('/api/query', methods=['GET', 'POST'])
def api_query():
    try:
        query = request.json.get('query')
        db_logging.log_search(query, request.json.get('referrer'))
        return jsonify({'products' : core.get_search_results(query), 'query': query})
    except Exception as e:
        print(f"ERROR: /api/query/{query}: ", e)
        return jsonify({'error' : 'ERROR'}), 500

# ============================= #
# Product                       #
# ============================= #
@app.route('/product/<string:slug>/<int:product_id>')
def web_product(slug, product_id):
    db_logging.log_product_click(product_id=product_id, referrer=request.referrer)
    product = core.get_product(product_id, user_id=g.user_id)
    if not product:
        return redirect('/')
        
    # TODO: Use is_wishlisted as part of the product itself. 
    return render_template('product.html', current_product=product, products=core.get_similar_products(product_id), is_wishlisted=product['is_wishlisted'])

@app.route('/api/product/<int:product_id>', methods=['GET', 'POST'])
def api_product(product_id):
    db_logging.log_product_click(product_id=product_id, referrer=request.json.get('referrer'))
    try:
        return jsonify({
            'product' : core.get_product(product_id=product_id, user_id=g.user_id),
            'similar_products' : core.get_similar_products(product_id),
            })
    except Exception as e:
        print(f"ERROR: /product/{product_id} failed:", e)
        return jsonify({"error": 'ERROR'}), 400

@app.route('/product')
def product_base():
    return "Welcome to Husn App Products!", 200
# ============================= #
# Wishlist                      #
# ============================= #
@app.route('/wishlist')
def wishlist():
    if not g.user_id:
        return redirect('/login-screen')
    wishlisted_products, err = core.get_wishlisted_products(g.user_id)
    if err:
        abort(500)
    return render_template('wishlist.html', products=wishlisted_products)

@app.route('/api/wishlist', methods = ['GET', 'POST'])
def api_wishlist():
    if not g.user_id:
        return '', 401
    wishlisted_products, err = core.get_wishlisted_products(g.user_id)
    if err:
        abort(500)
    return jsonify({'products' : wishlisted_products})

# ============================= #
# Toggle wishlist               #
# ============================= #
# TODO: rename endpoint to toggle wishlist
@app.route('/api/wishlist/<int:index>', methods=['POST'])
def toggle_wishlist_product(index):
    if not g.user_id:
        return '', 401
    wishlist_status, err = core.get_wishlisted_status(user_id=g.user_id, product_id=index)
    if err:
        return '', 500
    return jsonify({"wishlist_status": wishlist_status})
 
# ============================= #
# Login                         #
# ============================= #       
# Route for login
@app.route('/login')
def login():
    if g.user_id:
        return redirect('/')
    session['next_url'] = request.referrer or '/'
    redirect_uri = url_for('authorize', _external=True, _scheme=Config.PREFERRED_URL_SCHEME)
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
    return redirect('/')

# Route for logout
@app.route('/logout')
def logout():
    response = make_response(redirect('/'))
    return cookie_handler.get_logged_out_response(response)

# ============================= #
# Onboarding                    #
# ============================= #
@app.route('/onboarding', methods = ['GET', 'POST'])
def onboarding():
    if not g.user_id:
        return redirect('/login')
    if request.method == 'GET':
        return render_template('onboarding.html')
    
    if request.method == 'POST':
        if not core.complete_onboarding(age=request.form.get('age', 0), gender=request.form.get('gender', 0)):
            return redirect('/onboarding')
        
        return redirect('/')
    
@app.route('/api/onboarding', methods = ['POST'])
def api_onboarding():
    print(f"INFO: api_onboarding:{request.json=}")
    if not g.user_id:
        return '', 401
    
    if request.method == 'POST':
        if not core.complete_onboarding(age=request.json.get('age', 0), gender=request.json.get('gender', 0)):
            return '', 500
        return '', 200

@app.route('/api/applogin', methods = ['POST'])
def applogin():
    data = request.json
    idToken = data.get('idToken')
    sign_in_type = data.get('sign_in_type', 'GOOGLE')
    
    print(f"{idToken=}\n{sign_in_type=}")
    
    if sign_in_type == 'GOOGLE':
        user_info = id_token.verify_oauth2_token(idToken, google_api_requests.Request())
    elif sign_in_type == 'APPLE':
        user_info = apple_auth_handler.verify_apple_id_token(idToken)
        user_info['given_name'], user_info['family_name'] = data.get('given_name', ''), data.get('family_name', '')
        user_info['name'] = f"{user_info['given_name']} {user_info['family_name']}".strip()
    else:
        print("CRITICAL: Unexpecdted path")
        return '', 401
    
    try: 
        def get_device_type(aud):
            if aud == Config.ANDROID_CLIENT_ID:
                return 'ANDROID'
            if aud == Config.IOS_CLIENT_ID:
                return 'IOS'
            if aud == apple_auth_handler.IOS_BUNDLE_ID:
                return 'IOS-AppleSignIn'
            return None

        device_type = get_device_type(user_info['aud'])
        if not device_type:
            print('CRITICAL: Login attempt with Invalid client id: ', user_info['aud'])
    
        user = core.create_user_if_needed(user_info)
        
        print(f"INFO: {device_type} Login : {user.name=} | {user.email=} | {user.sub=}")
        
        cookie_handler.set_cookie_updates_at_login(user=user)
        return jsonify({"is_logged_in": True})
    except Exception as e:
        print(f"ERROR: Error in logging in: {e}")
        return jsonify({'is_logged_in': False}), 400

# ============================= #
# Profile & Account             #
# ============================= # 
@app.route('/api/profile', methods = ['POST'])
def api_profile():
    if not g.user_id:
        return '', 401
    try:
        user = core.get_full_user()
        assert user is not None, f"{user=}"
        return jsonify({
            'given_name' : user.given_name or '',
            'family_name' : user.family_name or '',
            'picture_url' : user.picture_url or '',
            'email' : user.email or '',
            'is_private_email' : user.is_private_email
        })
    except Exception as e:
        print("ERROR: error retrieving full user: ", e)
        return '', 500

@app.route('/api/delete_account', methods = ['POST'])
def api_delete_account():
    if not g.user_id:
        return '', 401
    
    try:
        user = core.get_full_user()
        user.onboarding_stage = None
        user.gender = None
        user.birth_year = None
        db.session.commit()
    except Exception as e:
        print("ERROR: Error deleting user: ", e)
    print(f"USER {g.user_id=} requested to delete their account.")
    return ''

@app.route('/downloadapp')
def download_app():
    user_agent = request.headers.get('User-Agent').lower()
    if 'android' in user_agent and Config.PLAY_STORE_URL:
        return redirect(Config.PLAY_STORE_URL)
    elif ('iphone' in user_agent or 'ipad' in user_agent) and Config.APP_STORE_URL:
        return redirect(Config.APP_STORE_URL)
    else:
        return redirect('/')

if __name__ == '__main__':
    app.run(debug=(Config.DEPLOYMENT_TYPE == 'LOCAL'))
