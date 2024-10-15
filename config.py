import os

basedir = os.path.abspath(os.path.dirname(__file__))
class Config(object):
    DEPLOYMENT_TYPE = os.environ.get('DEPLOYMENT_TYPE', 'LOCAL')
    DATA_ROOT_DIR = os.environ.get('DATA_ROOT_DIR', '/husn-cool-storage/20231014/') if (DEPLOYMENT_TYPE in ('PROD', 'DEV')) else './'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'Superecret'
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    REFRESH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    SESSION_COOKIE_HTTPONLY = True 
    DATABASE_TYPE = os.environ.get('DATABASE_TYPE')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'sqlite.db')
    if os.environ.get('DATABASE_URI') and DATABASE_TYPE == 'PROD':
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')
        
    # By default sqlalchemy doesn't recycle connections which can lead to "stale" connections.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600  # Recycle connections every hour (3600 seconds)
    }

        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Geed feed defaults.
    FEED_MINIMUM_CLICKS = os.environ.get('FEED_MINIMUM_CLICKS', 5)
    FEED_NUM_PRODUCTS = os.environ.get('FEED_NUM_PRODUCTS', 256)
    FEED_CLICK_SAMPLE = os.environ.get('FEED_CLICK_SAMPLE', 32)
    
    # Inspirations Path
    INSPIRATIONS_PATH = os.environ.get('INSPIRATIONS_PATH', '')