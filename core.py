import torch.nn.functional as F
import artifacts_loader
from models import WishlistItem, UserClick
from config import Config
import random


model, tokenizer = artifacts_loader.load_model_and_tokenizer()
products_df = artifacts_loader.load_products_df()
image_embeddings = artifacts_loader.load_image_embeddings()
faiss_index = artifacts_loader.load_faiss_index(image_embeddings)
similar_products_cache = artifacts_loader.load_similar_products_cache()
inspirations_obj = artifacts_loader.load_inspirations()


def is_wishlisted_product(product_id, user_id=None):
    if (not user_id) or (not product_id):
        return False
    return WishlistItem.query.filter_by(user_id=user_id, product_index=product_id).first() is not None

# DEPRECATED : Use faiss_index.search instead. 
def getTopK(base_embedding, K=100):
    global image_embeddings
    probs = F.cosine_similarity(image_embeddings, base_embedding.view(1, 512))
    topk_indices = probs.topk(K).indices
    return topk_indices, probs[topk_indices]

def get_search_results(query, n = 128):
    """Returns a list of n matching products or empty list if query is empty."""
    global tokenizer, faiss_index, products_df
    if not query:
        return []
    
    query_encoding = tokenizer(query)
    query_embedding = F.normalize(model.encode_text(query_encoding), dim=-1) # shape = [1, DIM]

    ## faiss_index.search expects batched inputs.
    topk_scores, topk_indices = faiss_index.search(query_embedding.detach().numpy(),  n + 1) 
    topk_scores, topk_indices = topk_scores[0], topk_indices[0]
    
    # Return top n products.
    return products_df.iloc[topk_indices].to_dict('records')
    
# TODO : Add wishlisted.
def get_product(product_id, user_id=None):
    """Returns the product for the product id, or None if product_id is invalid."""
    if product_id >= len(products_df):
        return None
    
    product = products_df.iloc[product_id].to_dict()
    product['is_wishlisted'] = is_wishlisted_product(product_id=product_id, user_id=user_id)
    return product

def get_similar_products(product_id, n = 128):
    """Returns a list of n similar products for the product_id or empty list if product_id is invalid."""
    global similar_products_cache, products_df

    if product_id >= similar_products_cache.shape[0]:
        return []
    topk_indices = similar_products_cache[product_id][:n]
    return products_df.iloc[topk_indices].to_dict('records')

def get_inspirations(gender):
    """Returns inspirations for the given gender or empty if gender is invalid."""
    global inspirations_obj
    gender = gender or 'WOMAN'
    gender = gender.upper()
    
    if gender not in ('MAN', 'WOMAN'):
        return []
    return inspirations_obj[gender]


def get_feed(user_id):
    global products_df
    
    # Get clicked products.
    clicks = UserClick.query.with_entities(UserClick.product_index, UserClick.clicked_at) \
        .filter_by(user_id=user_id) \
            .order_by(UserClick.clicked_at.desc()) \
                .distinct() \
                    .limit(Config.FEED_CLICK_SAMPLE) \
                        .all()
    clicked_products = [click.product_index for click in clicks]
    
    # Don't return results if user hasn't made some clicks yet.
    if len(clicked_products) < Config.FEED_MINIMUM_CLICKS:
        return []
    
    # sample feed porducts. 
    feed_products_indexes = list(set(similar_products_cache[clicked_products].view(-1).detach().tolist()))
    sampled_feed_indexes = random.sample(feed_products_indexes,
                                         min(Config.FEED_NUM_PRODUCTS, len(feed_products_indexes)))
    
    return products_df.iloc[sampled_feed_indexes].to_dict('records')