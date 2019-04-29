# -*- coding:utf-8 -*-
"""
某些函数必须检查返回值
检查消耗37.74 --》40.2
"""
import ast
import sys
from flake8_polyfill import options


try:
    from flake8.engine import pep8 as stdin_utils
except ImportError:
    from flake8 import utils as stdin_utils


class ReturnChecker(object):
    name = 'flake8_check_return'
    version = '1.0.0'
    assign_msg = 'R001 Should check return of method "{0}"'

    def __init__(self, tree, filename):
        self.tree = tree
        self.filename = filename

    def run(self):
        ''' 返回iterater of (line_number, offset, text, check) '''
        tree = self.tree

        if self.filename == 'stdin':
            lines = stdin_utils.stdin_get_value()
            tree = ast.parse(lines)

        visitor = CallVisitor(self)
        visitor.visit(self.tree)
        return iter(visitor.violations)

    @classmethod
    def add_options(cls, parser):
        options.register(
            parser,
            '--return-check-methods', default='', type='string',
            help='Names of the method should be checked return.',
            parse_from_config=True,
            comma_separated_list=True,
        )

    @classmethod
    def parse_options(cls, parsed_options):
        cls.return_check_methods = set(parsed_options.return_check_methods)


class CallVisitor(ast.NodeVisitor):
    def __init__(self, checker):
        super(CallVisitor, self).__init__()
        self._checker = checker
        self._result = []

    @property
    def violations(self):
    	return self._result

    def generic_visit(self, node):
        if not getattr(node, "_ignore", False):
            ast.NodeVisitor.generic_visit(self, node)

    def visit_If(self, if_node):
        """在if语句中的也需要判断"""
        # 将if语句中表达式部分不检查
        if_node.test._ignore = True
        ast.NodeVisitor.generic_visit(self, if_node)

    def visit_Assign(self, assign_node):
        """截断赋值操作"""

    def visit_Return(self, return_node):
        """截断有返回值的操作"""

    def visit_Call(self, call_node):
        # 已经忽略的节点不处理
        if not getattr(call_node, "_ignore", False):
            if isinstance(call_node.func, ast.Attribute) and call_node.func.attr in self._checker.return_check_methods:
                self._result.append(self.error(call_node, variable=(call_node.func.attr, )))
        ast.NodeVisitor.generic_visit(self, call_node)

    def error(
        self,
        statement,
        message=None,
        variable=None,
        line=None,
        column=None,
    ):
        if not message:
            message = self._checker.assign_msg
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
            type(self._checker),
        )