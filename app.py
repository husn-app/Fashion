from flask import Flask, jsonify, render_template, redirect, request, url_for, make_response, session
import open_clip
import pandas as pd
import time
import torch
import torch.nn.functional as F
import faiss
import json
from authlib.integrations.flask_client import OAuth
import requests
from .config import Config
from flask_login import LoginManager, login_user, current_user, login_required, logout_user
from .user import User
from .db import db
import os

DEPLOYMENT_TYPE = os.environ.get('DEPLOYMENT_TYPE', 'LOCAL')

ROOT_DIR = os.environ.get('DATA_ROOT_DIR', '/husn-cool-storage/20231014/') if (DEPLOYMENT_TYPE == 'PROD') else './'

torch.set_grad_enabled(False)
model, preprocess, tokenizer = None, None, None
final_df = None
image_embeddings = None
faiss_index = None
similar_products_cache = None

def init_model():
    global model, preprocess, tokenizer
    print('Initializing model...')
    start_time = time.time()
    model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
    model.visual = None
    model = torch.compile(model)
    tokenizer = open_clip.get_tokenizer('ViT-B-32')
    print('Initialized model.\tTime Taken: ', time.time() - start_time)


def init_final_df():
    global final_df
    print('Reading products data...')
    start_time = time.time()
    PRODUCTS_CSV_PATH = ROOT_DIR + 'products_minimal.csv'

    final_df = pd.read_csv(PRODUCTS_CSV_PATH)
    print('Read products data\tTime taken: ', time.time() - start_time)

def init_image_embeddings():
    global image_embeddings
    print('Reading image embeddings...')
    start_time = time.time()
    image_embeddings = F.normalize(torch.load(ROOT_DIR + 'image_embeddings_normalized.pt'), dim=-1).detach().numpy()
    print('Read image embeddings.\nTime Taken: ', time.time() - start_time)
    
def init_faiss_index():
    global faiss_index
    faiss_index = faiss.IndexFlatIP(512)
    faiss_index.add(image_embeddings) 

def init_ml():
    global similar_products_cache
    init_final_df()
    
    init_model()
    init_image_embeddings()
    init_faiss_index()
    similar_products_cache = torch.load(ROOT_DIR + 'similar_products_cache.pt')
    

init_ml()
# Assert model
assert model is not None
assert preprocess is not None
assert tokenizer is not None 
# Assert df
assert final_df is not None
# Assert embeddings
assert image_embeddings is not None
assert faiss_index is not None
assert similar_products_cache is not None

app = Flask(__name__)
app.config.from_object(Config)  
db.init_app(app)

# Initialize LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(id):
    try:
        return User.query.get(int(id))
    except ValueError:
        return None
    except Exception as ex:
        print(f"Couldnt load user:{ex}")

with app.app_context():
    db.create_all()

oauth = OAuth(app)
google = oauth.register(
    name='google',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={
        'scope': 'openid email profile',
        'access_type': 'offline',   # to get refresh token
        'prompt': 'consent',        # to ensure refresh token is received
    },
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
)

@app.route('/')
def home():
    return render_template('landingpage.html')

# DEPRECATED : Use faiss_index.search instead. 
def getTopK(base_embedding, K=100):
    global image_embeddings
    probs = torch.nn.functional.cosine_similarity(image_embeddings, base_embedding.view(1, 512))
    topk_indices = probs.topk(K).indices
    return topk_indices, probs[topk_indices]

def process_query(query):
    global tokenizer, faiss_index, final_df
    if not query:
        return None, "Query cannot be empty", 400
    
    query_encoding = tokenizer(query)
    query_embedding = F.normalize(model.encode_text(query_encoding), dim=-1) # shape = [1, DIM]

    ## faiss_index.search expects batched inputs.
    topk_scores, topk_indices = faiss_index.search(query_embedding.detach().numpy(),  100) 
    topk_scores, topk_indices = topk_scores[0], topk_indices[0]

    products = final_df.iloc[topk_indices].to_dict('records')
    return {"query": query, "products": products, "scores": topk_scores.tolist()}, None, 200

@app.route('/query/<query>')
def web_query(query):
    result, error, status_code = process_query(query)
    if error:
        return error, status_code
    return render_template('query.html', **result)

@app.route('/api/query', methods=['POST'])
def api_query():
    data = request.json
    query = data.get('query')
    result, error, status_code = process_query(query)
    if error:
        return jsonify({"error": error}), status_code
    return jsonify(result)

def process_product(index):
    global image_embeddings, final_df, similar_products_cache

    if isinstance(index, str) and index.startswith('myntra-'):
        index = index[len('myntra-'):]
        index = int(index)
        index_list = final_df[final_df['productId'] == index]['index'].tolist()
        if not index_list:
            return None, "Product not found", 404
        index = index_list[0]

    try:
        index = int(index)
    except ValueError:
        return None, "Invalid product index", 400

    # topk_indices, topk_scores = getTopK(image_embeddings[index])
     # We use cached similar products, instead of computing similarity online. 
    topk_indices = similar_products_cache[index][:100]

    products = final_df.iloc[topk_indices.tolist()].to_dict('records')
    current_product = final_df.iloc[index].to_dict()
    return {
        "current_product": current_product,
        "products": products,
        "topk_scores": []
    }, None, 200

@app.route('/product/<index>')
def web_product(index):
    result, error, status_code = process_product(index)
    if error:
        return redirect('/')
    return render_template('product.html', **result)

@app.route('/api/product/<index>')
def api_product(index):
    result, error, status_code = process_product(index)
    if error:
        return jsonify({"error": error}), status_code
    return jsonify(result)

def refresh_token():
    data = {
        "client_id": app.config['GOOGLE_CLIENT_ID'],
        "client_secret": app.config['GOOGLE_CLIENT_SECRET'],
        "refresh_token": current_user.refresh_token,
        "grant_type": "refresh_token"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(app.config['REFRESH_TOKEN_URL'], data=data, headers=headers)

    # Check the response
    if response.status_code != 200:
        print(f"Error: {response.status_code}\n{response.text}")
        return False
    
    token_data = response.json()
    print("New access token:", token_data)
    session['access_token'] = token_data.get('access_token')
    session['expires_at'] = (int)(time.time()) + token_data['expires_in']
    return True


def check_and_refresh_token():
    expires_at = session.get('expires_at')
    if not expires_at or expires_at < time.time():
        if not refresh_token():
            print(f"Refresh failed, redirect to /login. {session=}")
            return False
    return True

# Route for login
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect('/')
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri, access_type="offline") # needed for refresh token

# Route for authorization callback
@app.route('/authorize')
def authorize():
    print(f"{request.args=}")
    if current_user.is_authenticated:
        return redirect('/')
    
    print(f"{json.dumps(request.args, indent=4)}")
    token = google.authorize_access_token()
    print(f"{token=}\n {type(token)=}\n{type(google)=}")
    resp = google.get('userinfo')
    print(f"{resp=}")
    user_info = resp.json()
    print(f"{user_info=}")

    user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        print(f"user not found, creating in table")
        user = User(auth_id=user_info.get('id'), email=user_info.get('email'), name=user_info.get('name'),
                    given_name=user_info.get('given_name'), family_name=user_info.get('family_name'),
                    picture_url=user_info.get('picture'))
        db.session.add(user)
        print(f"Created {user=}")
    else:
        print(f"user found already in table:{user=}")
    user.refresh_token = token.get('refresh_token')
    db.session.commit()

    session['access_token'] = token.get('access_token')
    session['expires_at'] = token.get('expires_at')
    login_user(user)

    next_url = session.pop('next_url', '/')
    response = make_response(redirect(next_url))
    return response

# Route for logout
@app.route('/logout')
def logout():
    logout_user()
    session.pop('access_token', None)
    session.pop('expires_at', None)
    return redirect('/')

# Example protected route
@app.route('/profile')
@login_required
def profile():
    if check_and_refresh_token():
        return render_template('profile.html', user=current_user)
    session['next_url'] = request.url
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
