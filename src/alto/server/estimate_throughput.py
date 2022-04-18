"""
estimate_throughput.py

A Flask app that runs a basic ALTO server.

IMPORTANT NOTES:
* This script assumes that the configuration files are located at
	"input/g2.conf" and "output/input_routing.conf". If this is not the case,
	then change the variables g2fp_str and infp_str
* This script estimates RTT by summing up the delays of each link. This is
	not accurate!!! But, since taking into account queuing dynamics is
	too difficult, the script does this instead.
"""

import json
import numpy as np

NETWORK_TYPE = "G2_MININET"
"""The format in which the network is configured.

Currently, only `G2_MININET` is supported.
"""

SOLVER = "jensen"
"""The numerical optimizer that is used.

Currently, only `jensen` is supported.
"""

if __name__ == "__main__":
	from flask import Flask, request
	import json

	if SOLVER == "jensen":
		from solvers.jensen import solve

	app = Flask(__name__)

	# TODO: In the future, we will abstract out this code block into
	#	a proper plugin interface, that will allow the server to support a
	#	variety of network APIs in addition to G2_MININET.
	if NETWORK_TYPE == "G2_MININET":
		# TODO: depending on where this script is run from
		#	and where the files are
		#	you might want to change these paths

		g2fp_str = "input/g2.conf"
		infp_str = "output/input_routing.conf"

		g2fp = open(g2fp_str, "r")
		g2conf_str = g2fp.read()
		g2fp.close()

		infp = open(infp_str, "r")
		input_str = infp.read()
		infp.close()
        
		from g2mininet_parser import G2MininetParser
		parser = G2MininetParser(g2conf_str, input_str)

	alto_endpoint = "/endpoint/cost/"
	@app.route(alto_endpoint, methods=['POST'])
	def get_throughput():
		"""An endpoint that serves ALTO requests for network cost.

		Note:
			This function takes no Python args because it reads an HTTP
			request. This request must be according to the ALTO specification
			given in RFC 7285.

		Returns:
			The network cost map in the JSON format used by ALTO, as specified
			in RFC 7285.

		"""
		json = request.get_json()
		flows = json["endpoint-flows"]

		# make flows datastructure
		id_to_flow = []
		flow_to_id = {}

		i = 0

		for flow_set in flows:
			for src in flow_set["srcs"]:
				for dst in flow_set["dsts"]:
					id_to_flow.append(src, dst)
					flow_to_id[(src, dst)] = i
					i += 1

		flow_info = parser.construct_from_flows(id_to_flow)

		tput = solve(flow_info["A"], flow_info["c"], flow_info['RTT'])[0]

		tput_dict = {}
		for flow in id_to_flow:
			tput_dict[flow[0]] = {} # initialize each source to empty dict

		for i, cur_tput in enumerate(tput):
			src, dst = flow_to_id[i]
			tput_dict[src][dst] = cur_tput

		retval = {
			"endpoint-cost-map": tput_dict
		}

		response = flask.make_response(json.dumps(retval))
		response.headers['Content-Type'] = 'application/alto-endpointcost+json'
		return response

	app.run()
