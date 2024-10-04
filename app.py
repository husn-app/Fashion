from flask import Flask, jsonify, render_template, redirect, request
import open_clip
import pandas as pd
import time
import torch
import torch.nn.functional as F
import faiss

DEPLOYMENT_TYPE = os.environ.get('DEPLOYMENT_TYPE', 'LOCAL')

ROOT_DIR = '/husn-cool-storage/' if (DEPLOYMENT_TYPE == 'PROD') else './'

torch.set_grad_enabled(False)

model, preprocess, tokenizer = None, None, None
final_df = None
image_embeddings = None
faiss_index = None
similar_products_cached = None

def init_model():
    global model, preprocess, tokenizer
    print('Initializing model...')
    start_time = time.time()
    model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
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
    image_embeddings = F.normalize(torch.load(ROOT_DIR + 'image_embeddings_kaggle.pt'), dim=-1).detach().numpy()
    print('Read image embeddings.\nTime Taken: ', time.time() - start_time)
    
def init_faiss_index():
    global faiss_index
    faiss_index = faiss.IndexFlatIP(512)
    faiss_index.add(image_embeddings) 

def init_ml():
    global similar_products_cached
    init_final_df()
    
    init_model()
    init_image_embeddings()
    init_faiss_index()
    similar_products_cached = torch.load(ROOT_DIR + 'similar_products_cached.pt')
    

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
assert similar_products_cached is not None

app = Flask(__name__)

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
    global image_embeddings, final_df, similar_products_cached

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
    topk_indices = similar_products_cached[index][:100]

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

if __name__ == '__main__':
    app.run(debug=True)
