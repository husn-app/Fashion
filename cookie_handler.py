# Since it imports app. it must be imported in app.py after app's declaration.
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import g, request
from config import Config
from uuid import uuid4

assert Config.SECRET_KEY is not None
serializer = URLSafeTimedSerializer(Config.SECRET_KEY)
    
# We persist the session id across login / logouts.
def set_cookie_updates_for_new_session():
    if not g.session_id:
        g.session_id = str(uuid4())

    auth_cookie = serializer.dumps({
        'session_id' : g.session_id
    })
    g.cookie_updates = {
        'auth_info' : auth_cookie
    }

# app.before_request registered in app.py
def get_auth_info():
    g.cookie_updates = {}
    g.user_id, g.session_id = None, None
    cookies = request.cookies
    auth_cookie = cookies.get('auth_info')
    
    # New user.
    if not auth_cookie:
        set_cookie_updates_for_new_session()
        return
    
    # Existing user.    
    try:
        auth_cookie_decrypted = serializer.loads(auth_cookie, max_age=Config.MAX_COOKIE_AGE)
        g.user_id, g.session_id = auth_cookie_decrypted.get('user_id'), auth_cookie_decrypted.get('session_id')
        for key in ['picture_url', 'gender', 'onboarding_stage', 'email']:
            setattr(g, key, cookies.get(key))
    except SignatureExpired:
        # This shouldn't happen since cookies age is 100 years
        print("CRITICAL [Unexpected]: Logging out user because of expired signature.")
    except BadSignature:
        # Logout. If someone is tampering the cookies their user_id, session_id would be None. 
        g.cookie_updates.clear()
        print("CRITICAL: Someone tampered cookies or the secret key is wrong!")
        
# @app.after_request registered in app.py
def update_cookies(response):
    for key, value in g.cookie_updates.items():
        response.set_cookie(key, value, max_age=Config.MAX_COOKIE_AGE, httponly=True, secure=Config.SECURE_COOKIES)
    return response


def set_cookie_updates_at_login(user):
    auth_info = serializer.dumps({
        'user_id' : user.id,
        'session_id' : g.session_id or str(uuid.uuid4())
    })
    g.cookie_updates.update({
        'auth_info' : auth_info,
        'picture_url' : user.picture_url or '',
        'email' : user.email or '',
        'onboarding_stage' : user.onboarding_stage or 'PENDING'
    })
    if user.gender:
        g.cookie_updates.update({
            'gender': user.gender
        })
    
def update_cookies_at_onboarding(gender, onboarding_stage):
    g.cookie_updates.update({
        'gender' : gender,
        'onboarding_stage' : onboarding_stage
    })
    
def get_logged_out_response(response):
    # remove any cookie updates that may have been made. 
    g.cookie_updates.clear()
    
    for cookie in request.cookies:
        response.set_cookie(cookie, '', expires=0)
    # At this point we probably have g.session_id from get_auth_info, if nothing went unexpectedly wrong 
    set_cookie_updates_for_new_session()
    return response

