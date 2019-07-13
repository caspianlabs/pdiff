import os
import time 
import json

from flask import Flask
from flask import request, render_template, redirect, url_for, session
from flask_login import LoginManager, login_required, login_user, logout_user, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from requests_oauthlib import OAuth2Session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

class Auth:
    CLIENT_ID = os.environ.get('G_CLIENT_ID')
    CLIENT_SECRET = os.environ.get('G_CLIENT_SECRET')
    REDIRECT_URI = os.environ.get('G_REDIRECT_URI')
    REDIRECT_URI = 'http://localhost:5000/gCallback'
    AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
    TOKEN_URI = 'https://accounts.google.com/o/oauth2/token'
    USER_INFO = 'https://www.googleapis.com/userinfo/v2/me'
    SCOPE = 'profile email'


class Config:
    APP_NAME = "PDF Diff"
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = "postgresql://{0}:{1}@localhost/pdiff".format(
        os.environ.get('PG_USER'),
        os.environ.get('PG_PASSWORD')
    )

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"
Bootstrap(app)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    tokens = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def get_google_auth(state=None, token=None):
    if token:
        return OAuth2Session(Auth.CLIENT_ID, token=token)
    if state:
        return OAuth2Session(
            Auth.CLIENT_ID,
            state=state,
            redirect_uri=Auth.REDIRECT_URI)
    oauth = OAuth2Session(
        Auth.CLIENT_ID,
        redirect_uri=Auth.REDIRECT_URI,
        scope=Auth.SCOPE)
    return oauth

def pdiff(filename):
    command = "pdf-diff tmp/first.pdf tmp/second.pdf > static/{0}".format(filename)
    os.system(command)

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        f = request.files['first']
        f.save('tmp/first.pdf')
        f = request.files['second']
        f.save('tmp/second.pdf')
        filename = "compare-{0}.png".format(time.time())
        pdiff(filename)
        return redirect(url_for('compare', filename=filename))
    return render_template('index.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    google = get_google_auth()
    auth_url, state = google.authorization_url(
        Auth.AUTH_URI, access_type='offline')
    session['oauth_state'] = state
    r = google.get('https://www.googleapis.com/oauth2/v1/userinfo')
    print(r)
    return render_template('login.html', auth_url=auth_url)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
    
@app.route('/gCallback')
def callback():
    if current_user is not None and current_user.is_authenticated:
        return redirect(url_for('index'))
    if 'error' in request.args:
        if request.args.get('error') == 'access_denied':
            return 'You denied access.'
        return 'Error encountered.'
    if 'code' not in request.args and 'state' not in request.args:
        return redirect(url_for('login'))
    else:
        google = get_google_auth(state=session['oauth_state'])
        try:
            token = google.fetch_token(
                Auth.TOKEN_URI,
                client_secret=Auth.CLIENT_SECRET,
                authorization_response=request.url)
        except HTTPException:
            return 'HTTPError occured.'
        
        google = get_google_auth(token=token)
        resp = google.get(Auth.USER_INFO)
        if resp.status_code == 200:
            user_data = resp.json()
            print(user_data)
            if user_data['hd'] != 'launchdarkly.com':
                return 'Not authorized to view this page.'
            email = user_data['email']
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User()
                user.email = email
            user.first_name = user_data['given_name']
            user.tokens = json.dumps(token)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
        return 'Count not fetch your information.'

@app.route('/compare')
def compare():
    filename = request.args.get('filename')
    return render_template('output.html', filename=filename)
