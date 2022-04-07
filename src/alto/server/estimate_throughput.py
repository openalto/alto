"""
estimate_throughput.py

A Flask app that runs a basic ALTO server.

IMPORTANT NOTES:
* This script uses Jensen's numsolve script. numsolve must therefore be placed
	in the same directory as this script.
* This script assumes that the configuration files are located at
	"input/g2.conf" and "output/input_routing.conf". If this is not the case,
	then change the variables g2fp_str and infp_str
* This script estimates RTT by summing up the delays of each link. This is
	not accurate!!! But, since taking into account queuing dynamics is
	too difficult, the script does this instead.
"""

import json
import numpy as np

# stolen from testReader.py
def get_num_param(n, RTT, ccalg='cubic'):
	alpha, rho = None, None
	if ccalg == 'vegas':
		alpha = np.ones(n)
		rho = np.ones(n)
	elif ccalg == 'reno':
		alpha = [2] * n
		rho = [rtt**(-2) for rtt in RTT]
	elif ccalg == 'cubic':
		alpha = [4/3] * n
		rho = [rtt**(-1/3) for rtt in RTT]
	return alpha, rho

NETWORK_TYPE = "G2"

if __name__ == "__main__":
	from flask import Flask, request
	import json

	"""
	NOTE: numsolver has to be in the same directory as this file
	"""
	from numsolver import solve

	app = Flask(__name__)

	# TODO: depending on where this script is run from, and where the files are
	#	you might want to change these paths

	if NETWORK_TYPE == "G2":
		g2fp_str = "input/g2.conf"
		infp_str = "output/input_routing.conf"

		g2fp = open(g2fp_str, "r")
		g2conf_str = g2fp.read()
		g2fp.close()

		infp = open(infp_str, "r")
		input_str = infp.read()
		infp.close()
        
        from g2parser import G2Parser
		parser = G2Parser(g2conf_str, input_str)

	alto_endpoint = "/endpoint/cost/"
	@app.route(alto_endpoint, methods=['POST'])
	def get_throughput():
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

		"""
		The following code attempts to call the solver. Therefore, numsolver should
		be in the same directory as this code.
		"""
		alpha, rho = get_num_param(len(flow_info["RTT"]), flow_info["RTT"])
		# TODO: add f_lim and rate_limit?
		tput = solve(flow_info["A"], flow_info["c"], alpha, rho)[0]

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
