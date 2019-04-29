# -*- coding: utf-8 -*-
import ast
import sys


try:
    from flake8.engine import pep8 as stdin_utils
except ImportError:
    from flake8 import utils as stdin_utils


if sys.version_info >= (3, 0):
    PY3 = True
else:
    PY3 = False


class MutableDefaultsChecker(object):
    name = 'flake8_mutable_defaults'
    version = '1.0.0'
    assign_msg = 'K001 Function "{0}" has mutable defaults: named: "{1}"'

    def __init__(self, tree, filename):
        self.tree = tree
        self.filename = filename

    def run(self):
        ''' 返回iterater of (line_number, offset, text, check) '''
        tree = self.tree

        if self.filename == 'stdin':
            lines = stdin_utils.stdin_get_value()
            tree = ast.parse(lines)

        function_nodes = [ast.FunctionDef]
        if getattr(ast, 'AsyncFunctionDef', None):
            function_nodes.append(ast.AsyncFunctionDef)
        function_nodes = tuple(function_nodes)

        for statement in ast.walk(tree):
            value = None

            if isinstance(statement, function_nodes):
                value = self.check_function_definition(statement)

            if value:
                for line, offset, msg, rtype in value:
                    yield line, offset, msg, rtype

    def check_function_definition(self, statement):
        for idx, default in enumerate(statement.args.defaults):
            if isinstance(default, (ast.Dict, ast.List, ast.Set)) or\
                         (isinstance(default, ast.Call) and getattr(default.func, 'id', None)
                          in ("list", "dict", "set")):
                param_name = statement.args.args[-(idx + 1)].id
                yield self.error(default, variable=(statement.name, param_name))

    def error(
        self,
        statement,
        message=None,
        variable=None,
        line=None,
        column=None,
    ):
        if not message:
            message = self.assign_msg
        if not variable:
            variable = statement.id
        if not line:
            line = statement.lineno
        if not column:
            column = statement.col_offset

        return (
            line,
            column,
            message.format(*variable),
            type(self),
        )
