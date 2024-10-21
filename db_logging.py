from app import db
from models import UserClick
from flask import g
from config import Config

def is_bot():
    user_agent = request.headers.get('User-Agent', '').lower()
    for bot in Config.SCRAPING_BOTS:
        if bot in user_agent:
            return True
    return False

# TODO: Make this asynchronous. We don't care if we lose some of the clicks. 
def log_product_click(product_id, referrer=None):
    if is_bot():
        return
    user_click = UserClick(
        user_id=g.user_id, 
        session_id=g.session_id, 
        referrer=referrer, 
        product_index=product_id,
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )

    if Config.LOGGING_DESTINATION == 'DB':
        try:
            db.session.add(user_click)
            db.session.commit()
        except Exception as e:
            print(f"ERROR: Logging product click failed. {g.user_id=}, {product_id=}, {e=}")
    elif Config.LOGGING_DESTINATION == 'LOG':
        print(f"INFO: LOGGING {user_click=}")
    else:
        pass
        
        
def log_search(search_query, referrer=None):
    if is_bot():
        return

    user_click = UserClick(
        user_id=g.user_id, 
        session_id=g.session_id, 
        referrer=referrer, 
        search_query=search_query,
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    if Config.LOGGING_DESTINATION == 'DB':
        try:
            db.session.add(user_click)
            db.session.commit()
        except Exception as e:
            print(f"ERROR: Logging product click failed. {g.user_id=}, {search_query=}, {e=}")
    elif Config.LOGGING_DESTINATION == 'LOG':
        print(f"INFO: LOGGING {user_click=}")