import os
from config import Config
import open_clip
import pandas as pd
import torch
import torch.nn.functional as F
import faiss
from config import Config
import json
import time


def append_dashes_to_log(log, max_len=75, dash="="):
    log = "========= " + log + " "
    dash_count = max((max_len - len(log)), 0)
    return log + dash * dash_count
    
def log_funcall(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        print(append_dashes_to_log(f"Start {func.__name__}"))
        
        result = func(*args, **kwargs)
        
        end_time = time.time()
        print(append_dashes_to_log(f"Exit {func.__name__} : {int(end_time - start_time)}s"))
        return result
    return wrapper

@log_funcall
def load_model_and_tokenizer():
    model, _, _ = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
    model.visual = None
    model = torch.compile(model)
    tokenizer = open_clip.get_tokenizer('ViT-B-32')
    return model, tokenizer

@log_funcall
def load_products_df():
    return pd.read_csv(os.path.join(Config.DATA_ROOT_DIR, 'products_minimal.csv'))

@log_funcall
def load_image_embeddings():
    filename = os.path.join(Config.DATA_ROOT_DIR, 'image_embeddings_normalized.pt')
    image_embeddings = F.normalize(torch.load(filename, weights_only=True), dim=-1).detach().numpy()
    return image_embeddings
    
@log_funcall
def load_faiss_index(image_embeddings):
    faiss_index = faiss.IndexFlatIP(512)
    faiss_index.add(image_embeddings) 
    return faiss_index


@log_funcall
def load_similar_products_cache():
    return torch.load(os.path.join(Config.DATA_ROOT_DIR, 'similar_products_cache.pt'), weights_only=True)

@log_funcall
def load_inspirations():
    if Config.INSPIRATIONS_PATH:
        return json.load(open(Config.INSPIRATIONS_PATH))
    return {'MAN' : [], 'WOMAN' : []}
