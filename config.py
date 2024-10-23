import os

basedir = os.path.abspath(os.path.dirname(__file__))
class Config(object):
    DEPLOYMENT_TYPE = os.environ.get('DEPLOYMENT_TYPE', 'LOCAL')
    DATA_ROOT_DIR = os.environ.get('DATA_ROOT_DIR', '/husn-cool-storage/20231014/') if (DEPLOYMENT_TYPE in ('PROD', 'DEV')) else './'
    SECRET_KEY = os.environ.get('HUSN_SECRET_KEY')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    REFRESH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    SESSION_COOKIE_HTTPONLY = True 
    DATABASE_TYPE = os.environ.get('DATABASE_TYPE')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'sqlite.db')
    if os.environ.get('DATABASE_URI') and DATABASE_TYPE == 'PROD':
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')
    
    # NOTE: Database Disconnections : Read https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-optimistic
    # In case of higher pool_pre_ping trip we can completely disable it. Although between azure servers it should be super-fast <= 10ms.
    # pool_pre_ping is optimistic that it checks connection staleness before every query, and refreshes if needed. 
    # pool_recycles only refreshes when the time has elapsed. But the connection could be stale due to other reasons, like database restart / errors. 
    # in which case it'll still run into errors, **until probably the pool_recycle time has elapsed**. We can even keep it as low as 1 min?
    # But the session reconnnection is more costly - probably 200ms-300ms, and can overload if multiple sessions are being refreshed around the same time.
    # But it has the advantage of being called lesser number of times. 
    POOL_PRE_PING = (os.environ.get('POOL_PRE_PING', 'True').lower() == 'true')
    ANDROID_CLIENT_ID = os.environ.get('ANDROID_CLIENT_ID')
        
    # By default sqlalchemy doesn't recycle connections which can lead to "stale" connections.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': int(os.environ.get('POOL_RECYCLE', 15 * 60)),  # Recycle connections every 15 mins.
        'pool_pre_ping' : POOL_PRE_PING
    }
    
    SCRAPING_BOTS = os.environ.get('SCRAPING_BOTS', 'semrushbot,dataforseobot,ahrefsbot,amazonbot,googlebot,bingbot,openai.com')
    SCRAPING_BOTS = [x.strip() for x in SCRAPING_BOTS.split(',') if x.strip()]

        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Geed feed defaults.
    FEED_MINIMUM_CLICKS = os.environ.get('FEED_MINIMUM_CLICKS', 5)
    FEED_NUM_PRODUCTS = os.environ.get('FEED_NUM_PRODUCTS', 256)
    FEED_CLICK_SAMPLE = os.environ.get('FEED_CLICK_SAMPLE', 32)
    
    # Inspirations Path
    INSPIRATIONS_PATH = os.environ.get('INSPIRATIONS_PATH', '')
    
    # Cookies settings
    MAX_COOKIE_AGE = os.environ.get('MAX_COOKIE_AGE', 3600*24*365*10) # 10 year default
    SECURE_COOKIES = (DEPLOYMENT_TYPE != 'LOCAL')
    
    # http/https
    PREFERRED_URL_SCHEME = 'https' if (DEPLOYMENT_TYPE != 'LOCAL') else 'http'
    
    LOGGING_DESTINATION = os.environ.get('LOGGING_DESTINATION', 'LOG')