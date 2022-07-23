from flask import Flask, make_response, send_file

app = Flask(__name__)

@app.route('/topology')
def mn_topo():
    return send_file('mininet-topology.json')

@app.route('/restconf/operational/opendaylight-inventory:nodes/node/openflow:<swid>/table/0')
def of_table(swid):
    print(swid)
    return send_file('openflow%s.json' % (swid))

if __name__ == '__main__':
    app.run(port=8181)
