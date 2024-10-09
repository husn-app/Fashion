import os

basedir = os.path.abspath(os.path.dirname(__file__))
class Config(object):
    DEPLOYMENT_TYPE = os.environ.get('DEPLOYMENT_TYPE', 'LOCAL')
    DATA_ROOT_DIR = os.environ.get('DATA_ROOT_DIR', '/husn-cool-storage/20231014/') if (DEPLOYMENT_TYPE == 'PROD') else './'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'Superecret'
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    REFRESH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    SESSION_COOKIE_HTTPONLY = True 
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or \
        'sqlite:///' + os.path.join(basedir, 'sqlite.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False