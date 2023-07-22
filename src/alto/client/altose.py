from lark import Lark, Transformer

alto_se_parser = Lark('''
start: by id_list [where cond]

by: "BY" | "by"
id_list: [id_list ","] ID

where: "WHERE" | "where"
cond: [cond and] or_cond

or_cond: [or_cond or] atom_cond

atom_cond: value binop ID -> idr
         | ID binop value -> idl
         | ID binop ID -> idd
         | "(" cond ")" -> encap
         | not atom_cond -> neg

binop: "=" -> eq
     | "<" -> lt
     | "<=" -> lte
     | ">" -> gt
     | ">=" -> gte
     | "!=" -> ne

and: "AND" | "and" | "&"
or: "OR" | "or" | "|"

?value: NUMBER -> number
      | STRING -> string
      | boolean

?not: "NOT" | "not" | "!"
?boolean: true | false
?true: "TRUE" | "true"
?false: "FALSE" | "false"
ID: /[A-Za-z_][A-Za-z_0-9]*/

%import common.ESCAPED_STRING -> STRING
%import common.SIGNED_NUMBER -> NUMBER
%import common.WS
%ignore WS
''')

class SortingExpressionTransformer(Transformer):

    def __init__(self, cost_defs, prop_defs):
        Transformer.__init__(self)
        self.cost_defs = cost_defs
        self.prop_defs = prop_defs

    def start(self, items):
        id_list = items[1]
        cond_ids, func = items[3] if items[3] is not None else (set(), self.value_func(True))
        fdesc, flambda = func
        for item in items:
            print(item)

        return id_list, cond_ids, flambda, fdesc

    def id_list(self, items):
        prev = items[0] if items[0] is not None else []
        identifier = str(items[1])

        if identifier not in self.cost_defs:
            # TODO: raise an exception: identifier not defined as an ALTO cost
            sys.exit(1)

        return prev + [identifier]

    def cond(self, items):
        if items[0] is None:
            return items[2]
        ids1, f1 = items[0]
        ids2, f2 = items[2]
        return ids1 | ids2, self.compose_func('and', f1, f2)

    def or_cond(self, items):
        if items[0] is None:
            return items[2]
        ids1, f1 = items[0]
        ids2, f2 = items[2]
        return ids1 | ids2, self.compose_func('or', f1, f2)

    def cost_func(self, cost_name):
        return '%s(s, d)' % (cost_name), lambda s, d, res: res[cost_name][s][d]

    def prop_func(self, prop_name):
        return '%s(d)' % (prop_name), lambda s, d, res: res[prop_name][d]

    def value_func(self, value):
        return value, lambda s, d, res: value

    def map_to_func(self, is_id, id_value):
        if is_id:
            if id_value in self.cost_defs:
                return self.cost_func(id_value)
            elif id_value in self.prop_defs:
                return self.prop_func(id_value)
            else:
                # TODO: raise an exception: identifier not defined as an ALTO cost/prop
                sys.exit(1)
        else:
            return self.value_func(id_value)

    def compose_func(self, op, lf, rf):
        lfn, lf = lf
        rfn, rf = rf
        fname = "%s(%s, %s)" % (op, lfn, rfn)
        if op == 'eq':
            f = lambda s, d, res: lf(s, d, res) == rf(s, d, res)
        elif op == 'ne':
            f = lambda s, d, res: lf(s, d ,res) != rf(s, d, res)
        elif op == 'lt':
            f = lambda s, d, res: lf(s, d, res) < rf(s, d, res)
        elif op == 'lte':
            f = lambda s, d, res: lf(s, d, res) <= rf(s, d, res)
        elif op == 'gt':
            f = lambda s, d, res: lf(s, d, res) > rf(s, d, res)
        elif op == 'gte':
            f = lambda s, d, res: lf(s, d, res) >= rf(s, d, res)
        elif op == 'neg':
            f = lambda s, d, res: not (lf(s, d, res))
        elif op == 'and':
            f = lambda s, d, res: lf(s, d, res) & rf (s, d, res)
        elif op == 'or':
            f = lambda s, d, res: lf(s, d, res) | rf (s, d, res)
        else:
            # TODO: raise an exception: operator is not defined
            sys.exit(1)
        return fname, f


    def idl(self, items):
        id_name, op, value = items
        id_name, op = str(id_name), str(op)
        func = self.compose_func(op, self.map_to_func(True, id_name),
                                 self.map_to_func(False, value))
        return {id_name}, func

    def idr(self, items):
        print(items)
        value, op, id_name = items
        id_name, op = str(id_name), str(op)
        func = self.compose_func(op, self.map_to_func(False, value),
                                 self.map_to_func(True, id_name))
        return {id_name}, func

    def idd(self, items):
        id1, op, id2 = items
        id1, op, id2 = str(id1), str(op), str(id2)
        func = self.compose_func(op, self.map_to_func(True, id1),
                                 self.map_to_func(True, id2))
        return {str(id1), str(id2)}, func

    def encap(self, items):
        id_set, func = items[0]
        return id_set, func

    def neg(self, items):
        id_set, func = items[0]
        return id_set, self.compose_func('neg', func, None)

    eq = lambda s, _: "eq"
    lt = lambda s, _: "lt"
    lte = lambda s, _: "lte"
    gt = lambda s, _: "gt"
    gte = lambda s, _: "gte"
    ne = lambda s, _: "ne"
    neg = lambda s, _: "neg"
    true = lambda s, _: True
    false = lambda s, _: False

    STRING = lambda s, x: str(x)
    string = lambda s, x: str(x[0]).strip('""')
    NUMBER = lambda s, x: float(x)
    number = lambda s, x: float(x[0])
    boolean = bool

class SortingExpression(object):
    def __init__(self, exp, cost_defs, prop_defs):
        self.exp = exp
        self.cost_defs = cost_defs
        self.prop_defs = prop_defs

        self.cost_reqs = set()
        self.prop_reqs = set()
        self.key_func = None
        self.cond_func = None

    def parse(self, debug=False):
        try:
            ast = alto_se_parser.parse(self.exp)
        except Exception as e:
            import sys
            print(e)
            print("Error: failed to parse expression %s" % (exp))
            sys.exit(1)

        transformer = SortingExpressionTransformer(self.cost_defs, self.prop_defs)

        try:
            by, cond_ids, cond_func, cond_fdesc = transformer.transform(ast)
        except Exception as e:
            import sys
            print(e)
            print("Error: failed to interpret expression %s" % (exp))
            sys.exit(1)

        all_reqs = set(by) | set(cond_ids)
        self.cost_reqs = all_reqs & self.cost_defs.keys()
        self.prop_reqs = all_reqs & self.prop_defs.keys()
        self.key_func = lambda s, d, res: [res[x][s][d] for x in by]
        self.cond_func = cond_func

        if debug:
            print(cond_fdesc)

    def sort(self, res, pairs):
        filtered = [(s, d) for s, d in pairs if self.cond_func(s, d, res)]
        return sorted(filtered, key = lambda d: self.key_func(d[0], d[1], res))

if __name__ == '__main__':

    exp = 'BY geodist WHERE (country="UK")&(100>geodist)'
    se = SortingExpression(exp, {'geodist': {}}, {'continent': {}, 'country': {}})
    se.parse()

    ip1 = "192.168.1.2"
    ip2 = "192.168.2.2"
    ip3 = "192.168.3.2"
    ip4 = "192.168.4.2"

    res = {
        "geodist": { ip1: { ip3: 100, ip4: 50},
                     ip2: { ip3: 40, ip4: 75} },
        "country": {
            ip3: 'UK', ip4: 'FR'
        }
    }
    print(se.sort(res, [(i, j) for i in [ip1, ip2] for j in [ip3, ip4]]))
