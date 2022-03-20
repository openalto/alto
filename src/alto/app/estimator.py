"""
alto-estimator.py

Estimates the throughput of a number of different flows.

Can be used in two ways:

1. From other Python code. Call do_request(input_dict, alto_server)
    where input_dict is a Python dict representing the "endpoints-flows"
    argument, and where alto_server is the hostname of the ALTO server.
2. As a standalone script. In this case, --alto-server gives the hostname
    of the ALTO server, and --flows gives a path to an input file.
    The flows file is of the form
        SRC1 -> DST1 DST2 DST3 ...
        SRC2 -> DST4 DST5 DST6 ...
        ...

Note that, due to time constraints, this script does not make use of the
input compression made possible by Request Design 2.
"""

import json
import requests

def input_to_json(input_str):
    input_lines = input_str.splitlines()
    # no compression; TODO: compress
    ef_arr = []
    for line in input_lines:
        line_split = line.split("->")
        src = line_split[0].strip()
        dst_arr = line_split[1].strip().split(" ")
        dst_arr = list(filter(lambda a: a != 0, dst_arr))

        ef_arr.append({"srcs": [src], "dsts": dst_arr})
    return ef_arr

def do_request(input_dict, alto_server):
    alto_endpoint = "/endpoint/cost"
    query_json = {
        "cost-type": {"cost-mode" : "numerical",
                      "cost-metric" : "tput"},
        "endpoint-flows" : input_dict
    }
    query_str = json.dumps(query_json)
    query_headers = {
        "Content-Type": "application/alto-endpointcostparams+json",
        "Accept": "application/alto-endpointcost+json,application/alto-error+json"
    }
    alto_r = requests.post(alto_server + alto_endpoint,
        headers=query_headers,
        data=query_str
    )

    alto_json_resp = alto_r.json()
    return json.dumps(alto_json_resp)

def do_request_from_str(input_str, alto_server):
    return do_request(input_to_json(input_str), alto_server)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Estimate throughput for flows")
    parser.add_argument('--alto-server', required=True)
    parser.add_argument('--flows', required=True)
    args = parser.parse_args(sys.argv[1:])

    alto_server = args.alto_server

    fp = open(args.flows, "r")
    input_str = fp.read()
    fp.close()

    print(do_request_from_str(input_str, alto_server))
