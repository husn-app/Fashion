from app import db
from models import UserClick
from flask import g
from config import Config

# TODO: Make this asynchronous. We don't care if we lose some of the clicks. 
def log_product_click(product_id, referrer=None):
    user_click = UserClick(user_id=g.user_id, session_id=g.session_id, referrer=referrer, product_index=product_id)

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
    user_click = UserClick(user_id=g.user_id, session_id=g.session_id, referrer=referrer, search_query=search_query)
    if Config.LOGGING_DESTINATION == 'DB':
        try:
            db.session.add(user_click)
            db.session.commit()
        except Exception as e:
            print(f"ERROR: Logging product click failed. {g.user_id=}, {search_query=}, {e=}")
    elif Config.LOGGING_DESTINATION == 'LOG':
        print(f"INFO: LOGGING {user_click=}")