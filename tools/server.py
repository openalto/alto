from flask import Flask, send_file

app = Flask('alto-testserver')

@app.route('/networkmap')
def get_networkmap():
    return send_file('nm.json', mimetype='application/alto-networkmap+json')

@app.route('/costmap')
def get_costmap():
    return send_file('cm.json', mimetype='application/alto-costmap+json')

@app.route('/costmap/bw-available')
def get_costmap_bw_avail():
    return send_file('cm-bw.json', mimetype='application/alto-costmap+json')

@app.route('/costmap/delay-ow')
def get_costmap_delay_ow():
    return send_file('cm-delay.json', mimetype='application/alto-costmap+json')

app.run(host='0.0.0.0', port=8181)
