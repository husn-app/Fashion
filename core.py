import torch.nn.functional as F
import artifacts_loader
from models import WishlistItem, UserClick, User
from config import Config
import random
from app import db
from flask import g
import datetime
import cookie_handler

model, tokenizer = artifacts_loader.load_model_and_tokenizer()
products_df = artifacts_loader.load_products_df()
image_embeddings = artifacts_loader.load_image_embeddings()
faiss_index = artifacts_loader.load_faiss_index(image_embeddings)
similar_products_cache = artifacts_loader.load_similar_products_cache()
inspirations_obj = artifacts_loader.load_inspirations()

MAN, WOMAN = 'MAN', 'WOMAN'
ONBOARDING_COMPLETE = 'COMPLETE'

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
    
    def shuffled_inspirations(inspirations):
        for insp in inspirations:
            random.shuffle(insp['products'])
        random.shuffle(inspirations)
        return inspirations
    

    # Try to get gender from cookies. 
    gender = gender or g.get('gender')
    gender = gender or WOMAN
    gender = gender.upper()
    
    if gender not in (MAN, WOMAN):
        gender = WOMAN

    return shuffled_inspirations(inspirations_obj[gender]), gender.lower()

def get_default_feed(gender):
    global products_df
    feed_products_indexes = [product['index'] for insp in inspirations_obj[gender] for product in insp['products']]
    sampled_feed_indexes = random.sample(feed_products_indexes,
                                         min(Config.FEED_NUM_PRODUCTS, len(feed_products_indexes)))
    return products_df.iloc[sampled_feed_indexes].to_dict('records')

def get_feed(user_id):
    global products_df
    
    # TODO : Only on /api/feed. This is only for early testing for iOS. Remove.
    if not user_id:
        return get_default_feed(WOMAN)
    
    # Get clicked products.
    clicks = UserClick.query.with_entities(UserClick.product_index, UserClick.clicked_at) \
        .filter_by(user_id=user_id) \
        .filter(UserClick.product_index.isnot(None)) \
        .order_by(UserClick.clicked_at.desc()) \
        .distinct() \
        .limit(Config.FEED_CLICK_SAMPLE) \
        .all()
    clicked_products = [click.product_index for click in clicks]
    
    # Return feed from inspirations if user hasn't made some clicks yet.
    if len(clicked_products) < Config.FEED_MINIMUM_CLICKS:
        return get_default_feed(gender=(g.get('gender') or WOMAN)) # g.gender=None => g.get('gender', WOMAN) = None
    
    # sample feed porducts. 
    feed_products_indexes = list(set(similar_products_cache[clicked_products].view(-1).detach().tolist()))
    sampled_feed_indexes = random.sample(feed_products_indexes,
                                         min(Config.FEED_NUM_PRODUCTS, len(feed_products_indexes)))
    
    return products_df.iloc[sampled_feed_indexes].to_dict('records')


def create_user_if_needed(user_info):
    try:
        user = User.query.filter_by(email=user_info['email']).first()
        if user:
            return user
        user = User(auth_id=user_info.get('id'), email=user_info.get('email'), name=user_info.get('name'),
                    given_name=user_info.get('given_name'), family_name=user_info.get('family_name'),
                    picture_url=user_info.get('picture'))
        db.session.add(user)
        print(f"INFO: Created {user=}")
        db.session.commit()
        return user
    except Exception as e:
        print(f"CRITICAL : User couldn't login. {user_info=}, {e=}")
    return None

def get_full_user():
    if not g.user_id:
        return None
    if g.current_user:
        return g.current_user

    g.current_user = None
    try:
        g.current_user = User.query.filter_by(id=g.user_id).first()
    except ValueError as e:
        print(f"CRITICAL: Incorrect user_id in cookies. {g.user_id=}, {e=}")
    except Exception as e:
        print(f"CRITICAL: Can't fetch full user {g.user_id=}, {e=}")
        
    return g.current_user

def get_wishlisted_products(user_id):
    global products_df
    if not user_id:
        return [], "User not authenticated"
    try:
        wishlisted_products = db.session.query(WishlistItem.product_index).filter_by(user_id=user_id).order_by(WishlistItem.created_at.desc()).all()
        wishlisted_valid_indices = [index[0] for index in wishlisted_products if index[0] < len(products_df)]
        return products_df.iloc[wishlisted_valid_indices].to_dict('records'), None
    except Exception as e:
        print(f'ERROR: fetching wishlist {user_id=}, {e=}')
        return [], e
    
def get_wishlisted_status(user_id, product_id):
    try:
        wishlist_item = WishlistItem.query.filter_by(user_id=user_id, product_index=product_id).first()
        if wishlist_item:
            # Item exists, so remove it from the wishlist
            db.session.delete(wishlist_item)
            db.session.commit()
            print(f"INFO: Item removed from wishlist, {user_id=}, {product_id=}")
            return False, None
            # Item does not exist, so add it to the wishlist

        new_item = WishlistItem(user_id=user_id, product_index=product_id)
        db.session.add(new_item)
        db.session.commit()
        print(f"INFO Item added to wishlist. {user_id=}, {product_id=}")
        return True, None
    except Exception as e:
        return False, e
    
def complete_onboarding(age, gender):
    try:
        gender, age = str(gender), int(age)
        assert gender in (MAN, WOMAN)
        assert age >= 12 and age <= 72
    except:
        print(f"CRITICAL: Error parsing {gender=} and {age=}")
        return False
    
    try:
        user = User.query.get(g.user_id)
        user.gender = gender
        user.birth_year = datetime.datetime.now().year - age
        user.onboarding_stage = ONBOARDING_COMPLETE
        
        db.session.commit()
    except Exception as e:
        print('ERROR: Error commiting onboarding data to db: ', e)
        return False
    
    # Update cookies. 
    cookie_handler.update_cookies_at_onboarding(gender=gender, onboarding_stage=ONBOARDING_COMPLETE)
    return True