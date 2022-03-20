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

def parse_line(line):
    line_split = line.split(":")
    # line_split[0] is the field name, e.g. "links"
    line_val = line_split[1].strip()
    lines = list(map(lambda s: s.strip(), line_val.split(';')))
    lines = list(filter(lambda a: len(a) > 0, lines))
    return lines

def make_link_to_id(links_str):
    tuple_strs = parse_line(links_str)
    link_to_id = {}
    for tuple_str in tuple_strs:
        tuple_str = tuple_str[1:-1] #remove parens
        tuple_split = tuple_str.split(",")

        if len(tuple_split) != 3:
            continue
        link_id = int(tuple_split[0].strip())

        src = tuple_split[1].strip()
        dst = tuple_split[2].strip()
        link_to_id[(src, dst)] = link_id

        src = tuple_split[2].strip()
        dst = tuple_split[1].strip()
        link_to_id[(src, dst)] = link_id
    return link_to_id

def construct_routing_col(link_to_id, path):
    link_num = max(link_to_id.values())
    col = np.zeros((link_num+1,1)) # links are 1-indexed, so link_num+1
    for i in range(len(path)-1):
        cur_link = link_to_id[(path[i], path[i+1])]
        col[cur_link] = 1
    return col

def construct_routing_matrix(link_to_id, path_json, flows):
    # flows given as [(src, dst)...]
    # flows are zero-indexed, unlike links
    link_num = max(link_to_id.values())
    mat = np.zeros((link_num+1, len(flows)))
    for i, flow in enumerate(flows):
        src = flow[0]
        dst = flow[1]

        path = path_json[src][dst]
        col = construct_routing_col(link_to_id, path)
        mat[:,i] = col[:,0]
    return mat

def construct_cap_vector(
    link_to_id,
    link_info_str=None,
    default_link_info_str=None):

    assert(link_info_str is not None or default_link_info_str is not None)

    default_bw = 0
    if default_link_info_str is not None:
        default_bw = int(parse_line(default_link_info_str)[0][0].strip())

    link_num = max(link_to_id.values())
    cap_vector = [default_bw for i in range(link_num+1)]

    if link_info_str is not None:
        link_info_list = parse_line(link_info_str)
        for i, cur_link_info in enumerate(link_info_list):
            cur_link_info = cur_link_info.split(',')
            src = cur_link_info[0].strip()
            dst = cur_link_info[1].strip()
            cur_bw = int(cur_link_info[2].strip())
            cap_vector[link_to_id[(src, dst)]] = cur_bw

    return cap_vector

def construct_delay_dict(link_info_str=None, default_link_info_str=None):
    assert(link_info_str is not None or default_link_info_str is not None)

    default_bw = 0
    if default_link_info_str is not None:
        default_bw = int(parse_line(default_link_info_str)[0][0].strip())

    delay_dict = {}

    if link_info_str is not None:
        link_info_list = parse_line(link_info_str)
        for i, cur_link_info in enumerate(link_info_list):
            cur_link_info = cur_link_info.split(',')

            src = cur_link_info[0].strip()
            dst = cur_link_info[1].strip()
            delay = float(cur_link_info[3].strip().replace("ms",""))
            delay_dict[(src, dst)] = delay

            src = cur_link_info[1].strip()
            dst = cur_link_info[0].strip()
            delay = float(cur_link_info[3].strip().replace("ms",""))
            delay_dict[(src, dst)] = delay

    return delay_dict

def get_path_delay(delay_dict, path):
    c = 0
    for i in range(len(path)-1):
        c += delay_dict[(path[i], path[i+1])]
    return c

def get_flows_delay(delay_dict, path_json, flows):
    # flows given as [(src, dst)...]
    delay_vec = [0 for i in range(len(flows))]
    for i, flow in enumerate(flows):
        src = flow[0]
        dst = flow[1]

        path = path_json[src][dst]
        delay = get_path_delay(delay_dict, path)
        delay_vec[i] = delay
    return delay_vec

def construct_from_strings_and_flows(g2conf_str, input_str, flows):
    g2conf_lines = g2conf_str.splitlines()
    path_json = json.loads(input_str)

    link_info_str = None
    default_link_info_str = None
    links_str = None

    for line in g2conf_lines:
        if line.startswith("link_info:"):
            link_info_str = line
        elif line.startswith("default_link_info:"):
            default_link_info_str = line
        elif line.startswith("links:"):
            links_str = line

        if link_info_str is not None\
            and default_link_info_str is not None\
            and links_str is not None:
            break

    link_to_id = make_link_to_id(links_str)
    delay_dict = construct_delay_dict(link_info_str, default_link_info_str)

    cap_vector = construct_cap_vector(link_to_id,
        link_info_str,
        default_link_info_str)
    mat = construct_routing_matrix(link_to_id, path_json, flows)
    delay_vec = get_flows_delay(delay_dict, path_json, flows)

    return {
        "c": cap_vector,
        "A": mat,
        "RTT": delay_vec
    }

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

if __name__ == "__main__":
    from flask import Flask, request, make_response
    import json
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Server for throughput prediction")
    parser.add_argument('topo')
    parser.add_argument('routing')
    args = parser.parse_args(sys.argv[1:])

    print(args.topo)
    print(args.routing)

    """
    NOTE: numsolver has to be in the same directory as this file
    """
    from .numsolver import solve

    app = Flask(__name__)

    # TODO: depending on where this script is run from, and where the files are
    #    you might want to change these paths
    g2fp_str = args.topo
    infp_str = args.routing

    g2fp = open(g2fp_str, "r")
    g2conf_str = g2fp.read()
    g2fp.close()

    infp = open(infp_str, "r")
    input_str = infp.read()
    infp.close()

    alto_endpoint = "/endpoint/cost/"
    @app.route(alto_endpoint, methods=['POST'])
    def get_throughput():
        params = request.get_json()

        flows = params["endpoint-flows"]

        # make flows datastructure
        id_to_flow = []
        flow_to_id = {}

        i = 0

        for flow_set in flows:
            for src in flow_set["srcs"]:
                for dst in flow_set["dsts"]:
                    id_to_flow.append((src, dst))
                    flow_to_id[(src, dst)] = i
                    i += 1

        flow_info = construct_from_strings_and_flows(
            g2conf_str,
            input_str,
            id_to_flow
        )

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
            src, dst = id_to_flow[i]
            tput_dict[src][dst] = cur_tput

        retval = {
            "endpoint-cost-map": tput_dict
        }

        response = make_response(json.dumps(retval))
        response.headers['Content-Type'] = 'application/alto-endpointcost+json'
        return response

    app.run()
