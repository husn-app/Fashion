from config import Config

## Assert google auth configs.
assert Config.GOOGLE_CLIENT_ID is not None
assert Config.GOOGLE_CLIENT_SECRET
assert Config.ANDROID_CLIENT_ID

def get_google_oauth(oauth):
    return oauth.register(
        name='google',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        client_kwargs={
            'scope': 'openid email profile', # https://www.googleapis.com/auth/user.birthday.read https://www.googleapis.com/auth/user.gender.read',
        },
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        include_granted_scopes=True
    )
    
def get_user_info(google_oauth):
    try:
        _ = google_oauth.authorize_access_token()
        resp = google_oauth.get('userinfo')
        user_info = resp.json()
        print(f"INFO: Google-Authorize:{user_info=}")
        return user_info
    except Exception as e:
        print(f"ERROR: Error in getting user's google info {e}")
    return None