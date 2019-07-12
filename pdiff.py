import os
import time 

from flask import Flask
from flask import request, render_template, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__, static_url_path='')

def pdiff(filename):
    command = "pdf-diff tmp/first.pdf tmp/second.pdf > static/{0}".format(filename)
    os.system(command)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.files['first']
        f.save('tmp/first.pdf')
        f = request.files['second']
        f.save('tmp/second.pdf')
        filename = "compare-{0}.png".format(time.time())
        pdiff(filename)
        return redirect(url_for('compare', filename=filename))
    return '''
    <!doctype html>
    <title>Compare Two PDFs</title>
    <h1>Compare Two PDFs</h1>
    <form method=post enctype=multipart/form-data>
      <label>First Contract:</label>
      <input type=file name=first>
      <br />
      <br />
      <label>Second Contract:</label>
      <input type=file name=second>
      <br />
      <br />
      <input type=submit value=Compare>
    </form>
    '''

@app.route('/compare')
def compare():
    filename = request.args.get('filename')
    return render_template('output.html', filename=filename)