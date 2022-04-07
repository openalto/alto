import json

class G2Parser:
	def __init__(self, g2conf_str, input_str):
		self.g2conf_str = g2conf_str
		self.input_str = input_str

	def parse_line(self, line):
		line_split = line.split(":")
		# line_split[0] is the field name, e.g. "links"
		line_val = line_split[1].strip()
		return line_val.split(';')
	
	def make_link_to_id(self, links_str):
		tuple_strs = self.parse_line(links_str)
		link_to_id = {}
		for tuple_str in tuple_strs:
			tuple_str = tuple_str[1:-1] #remove parens
			tuple_split = tuple_str.split(",")

			link_id = int(tuple_split[0].strip())
			src = tuple_split[1].strip()
			dst = tuple_split[2].strip()

			link_to_id[(src, dst)] = link_id
		return link_to_id

	
	def construct_routing_col(self, link_to_id, path):
		link_num = max(link_to_id.values)
		col = np.zeros((link_num+1,1)) # links are 1-indexed, so link_num+1
		for i in range(len(path)-1):
			cur_link = link_to_id[(path[i], path[i+1])]
			col[cur_link] = 1
		return col

	
	def construct_routing_matrix(self, link_to_id, path_json, flows):
		# flows given as [(src, dst)...]
		# flows are zero-indexed, unlike links
		link_num = max(link_to_id.values)
		mat = np.zeros((link_num+1, len(flows)))
		for i, flow in enumerate(flows):
			src = flow[0]
			dst = flow[1]

			path = path_json[src][dst]
			col = self.construct_routing_col(link_to_id, path)
			mat[:,i] = col[:,0]
		return mat

	
	def construct_cap_vector(self,
		link_to_id,
		link_info_str=None,
		default_link_info_str=None):

		assert(link_info_str is not None or default_link_info_str is not None)

		default_bw = 0
		if default_link_info_str is not None:
			default_bw = int(self.parse_line(link_info_str)[0][0].strip())

		link_num = max(link_to_id.values)
		cap_vector = [default_bw for i in range(link_num+1)]

		if link_info_str is not None:
			link_info_list = self.parse_line(link_info_str)
			for i, cur_link_info in enumerate(link_info_list):
				src = cur_link_info[0].strip()
				dst = cur_link_info[1].strip()
				cur_bw = int(cur_link_info[2].strip())
				cap_vector[link_to_id[(src, dst)]] = cur_bw

		return cap_vector

	def construct_delay_dict(self, link_info_str=None, default_link_info_str=None):
		assert(link_info_str is not None or default_link_info_str is not None)

		default_bw = 0
		if default_link_info_str is not None:
			default_bw = int(self.parse_line(link_info_str)[0][0].strip())

		delay_dict = {}

		if link_info_str is not None:
			link_info_list = self.parse_line(link_info_str)
			for i, cur_link_info in enumerate(link_info_list):
				src = cur_link_info[0].strip()
				dst = cur_link_info[1].strip()
				delay = float(cur_link_info[3].strip().replace("ms",""))
				delay_dict[(src, dst)] = delay

		return delay_dict

	def get_path_delay(self, delay_dict, path):
		c = 0
		for i in range(len(path)-1):
			c += delay_dict[(path[i], path[i+1])]
		return c

	def get_flows_delay(self, delay_dict, path_json, flows):
		# flows given as [(src, dst)...]
		delay_vec = [0 for i in range(len(flows))]
		for i, flow in enumerate(flows):
			src = flow[0]
			dst = flow[1]

			path = path_json[src][dst]
			delay = self.get_path_delay(delay_dict, path)
			delay_vec[i] = delay
		return delay_vec

	def construct_from_flows(self, flows):
		g2conf_lines = lines(self.g2conf_str)
		path_json = json.loads(self.input_str)

		link_info_str = None
		default_link_info_str = None
		links_str = None

		for line in g2conf_lines:
			if line.startswith("link_info:"): link_info_str = line
			elif line.startswith("default_link_info:"):
				default_link_info_str = line
			elif line.startswith("links:"):
				links_str = line

			if link_info_str is not None\
				and default_link_info_str is not None\
				and links_str is not None:
				break

		link_to_id = self.make_link_to_id(links_str)
		delay_dict = self.construct_delay_dict(link_info_str, default_link_info_str)

		cap_vector = self.construct_cap_vector(link_to_id,
			link_info_str,
			default_link_info_str)
		mat = self.construct_routing_matrix(link_to_id, path_json, flows)
		delay_vec = self.get_flows_delay(delay_dict, path_json, flows)

		return {
			"c": cap_vector,
			"A": mat,
			"RTT": delay_vec
		}
