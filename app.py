
from flask import Flask, jsonify, render_template, redirect, request, url_for, make_response, session, g, abort

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
import datetime
import google_auth_handler

app = Flask(__name__)
app.config.from_object(Config) 
print(f"using {app.config['DEPLOYMENT_TYPE']=}\n{app.config['DATABASE_TYPE']=}, {app.config['POOL_PRE_PING']=}") 

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

@app.route('/api/feed')
def api_feed():
    if not g.user_id:
        return '', 401
    return jsonify({'products' : core.get_feed(g.user_id)})

# ============================= #
# Inspirations                  #
# ============================= #
@app.route('/inspiration', defaults={'gender': None})
@app.route('/inspiration/<path:gender>')
def web_inspirations(gender):
    inspirations, gender = core.get_inspirations(gender=gender)
    return render_template('inspirations.html', inspirations=inspirations, gender=gender)

@app.route('/api/inspiration', defaults={'gender': None})
@app.route('/api/inspiration/<path:gender>')
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
    return render_template('query.html', products=core.get_search_results(query))

@app.route('/api/query')
def api_query():
    try:
        query = request.json.get('query')
        db_logging.log_search(query, request.json.get('referrer'))
        return jsonify({'products' : core.process_query(query)})
    except Exception as e:
        return jsonify({'error' : e}), 500

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

@app.route('/api/product/<int:product_id>')
def api_product(product_id):
    db_logging.log_product_click(product_id=product_id, referrer=request.json.get('referrer'))
    try:
        return jsonify({
            'product' : core.get_product(product_id=product_id, user_id=g.user_id),
            'similar_products' : core.get_similar_products(product_id),
            })
    except Exception as e:
        return jsonify({"error": e}), 400

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

@app.route('/api/wishlist')
def api_wishlist():
    if not g.user_id:
        return '', 401
    wishlisted_products, err = core.get_wishlisted_products(g.user_id)
    if err:
        abort(500)
    return jsonify({'wishlisted_products' : wishlisted_products})

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
    return redirect(next_url)

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
    if not g.user_id:
        return '', 501
    
    if request.method == 'POST':
        if not core.complete_onboarding(age=request.json.get('age', 0), gender=request.json.get('gender', 0)):
            return '', 500
        return '', 200

if __name__ == '__main__':
    app.run(debug=(Config.DEPLOYMENT_TYPE == 'LOCAL'))
