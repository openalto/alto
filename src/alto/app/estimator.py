"""
alto-estimator.py

Estimates the throughput of a number of different flows.

Can be used as a standalone script. --alto-server gives the hostname
    of the ALTO server, and --flows gives a path to an input file.
    The flows file is of the form
        SRC1 -> DST1 DST2 DST3 ...
        SRC2 -> DST4 DST5 DST6 ...
        ...
"""

import json
import requests

def input_to_json(input_str):
    """Converts a string, representing a list of flows,
    into a dict that can be converted to JSON and sent to an ALTO server.

    Args:
        input_str (str): A string representing a list of flows.
            The list of flows should be of the form:
                SRC1 -> DST1 DST2 DST3 ...
                SRC2 -> DST4 DST5 DST6 ...
                ...
    
    Returns:
        A list of flows.
    """
    input_lines = input_str.splitlines()
    """
    TODO: add compression. https://github.com/openalto/alto/issues/7
    What does "compression" mean in this context? As was decided during a
        meeting before the hackathon (although I can't find the Google Doc
        in which this decision was made), the format of requests should
        allow flows to be specified by specifying a many-to-many relationship
        between sources and destinations. An example is as follows:

        {"srcs": ["src1", "src2", "src3"], "dsts": ["dst1", "dst2"]}

        The above dict defines six flows: one flow from each source to each
        destination.
    
    Now, this format was chosen to allow for the compression of requests.
        However, the input format groups flows by source. Thus, an input like

        SRC1 -> DST1 DST2
        SRC2 -> DST1 DST2
        SRC3 -> DST1 DST2

        can be compressed to the dictionary given above. But this code doesn't
        currently do that. The problem of finding an optimal compression
        strikes me as NP-hard (although I haven't actually thought it through).
        Thus, the current code simply naively translates the input string into
        a dict.
    """
    ef_arr = []
    for line in input_lines:
        line_split = line.split("->")
        src = line_split[0].strip()
        dst_arr = line_split[1].strip().split(" ")
        dst_arr = list(filter(lambda a: a != 0, dst_arr))

        ef_arr.append({"srcs": [src], "dsts": dst_arr})
    return ef_arr

from alto.client import Client

def do_request_from_str(input_str, alto_server):
    """Obtains ALTO throughput data for an input string representing flows
        of interest.

    Args:
        input_str (str): A string representing a list of flows.
            The list of flows should be of the form:
                SRC1 -> DST1 DST2 DST3 ...
                SRC2 -> DST4 DST5 DST6 ...
                ...

        alto_server (str): The base URL for the ALTO server. This URL cannot
            end in a "/".

    Returns:
        A JSON string representing the throughput for each flow
    """
    c = Client()
    return c.get_throughput(input_to_json(input_str), url=alto_server+"/endpoint/cost")

if __name__ == "__main__":
    """Obtains ALTO throughput data for an input file representing flows
        of interest.

    Args:
        --flows (str): A path to a list of flows.
            The list of flows should be of the form:
                SRC1 -> DST1 DST2 DST3 ...
                SRC2 -> DST4 DST5 DST6 ...
                ...

        --alto-server (str): The base URL for the ALTO server. This URL cannot
            end in a "/".

    Returns:
        A JSON string representing the throughput for each flow
    """
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
