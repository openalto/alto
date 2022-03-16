from flask import Flask, send_file

app = Flask('alto-testserver')

@app.route('/networkmap')
def get_networkmap():
    return send_file('nm.json', mimetype='application/alto-networkmap+json')

@app.route('/costmap')
def get_costmap():
    return send_file('cm.json', mimetype='application/alto-costmap+json')

app.run(port=8181)
