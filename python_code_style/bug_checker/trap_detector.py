# -*- coding:utf-8 -*-
"""
对python代码潜在bug的检查
"""

import ast
from contextlib import contextmanager
from flake8_polyfill import options

__version__ = '1.0'

TD001 = 'TD001 Function "{0}" has mutable defaults: named: "{1}"'
TD002 = 'TD002 Function "{0}" has call defaults: named: "{1}"'
TD003 = 'TD003 python do not support ++i, --i'
TD004 = 'TD004 do not define __del__ in class {0}'
TD005 = 'TD005 class {0} should not be old style class'
TD006 = 'TD006 must check return of method "{0}"'
TD007 = 'TD007 should not include chinese char'


def visit_node_recursive(node, visitor):
    for child_node in ast.walk(node):
        visitor(child_node)


@contextmanager
def add_attribute_temp(node, attr_name, attr_value=True):
    setattr(node, attr_name, attr_value)
    try:
        yield
    except BaseException:
        raise
    finally:
        delattr(node, attr_name)


@contextmanager
def add_attribute_recursive_temp(node, ast_type, attr_name, attr_value=True):
    '''给所有ast_type的child node增加临时属性'''
    visit_node_recursive(node, lambda e: isinstance(e, ast_type) and setattr(e, attr_name, attr_value))
    try:
        yield
    finally:
        visit_node_recursive(node, lambda e: isinstance(e, ast_type) and delattr(e, attr_name))


class StateDes(object):
    def __init__(self, attr):
        self.attr = attr

    def __get__(self, instance, typ):
        return instance.__dict__[self.attr]


class StateHelper(object):
    '''中间状态的记录'''
    ignore_return_check = StateDes('_ignore_return_check')

    def __init__(self):
        self._ignore_return_check = False

    @contextmanager
    def hold_state_ignore_return_check(self):
        with self._hold_state_bool('_ignore_return_check'):
            yield

    @contextmanager
    def _hold_state_bool(self, state):
        assert state[0] == '_' and hasattr(self, state)
        setattr(self, state, True)
        try:
            yield
        finally:
            setattr(self, state, False)

    @contextmanager
    def hold_state_func(self, enter_fn, outer_fn):
        enter_fn()
        try:
            yield
        finally:
            outer_fn()


class MixedVisitor(ast.NodeVisitor):
    def __init__(self, checker):
        super(MixedVisitor, self).__init__()
        self._checker = checker
        self._result = []
        self._state = StateHelper()

    def generic_visit(self, node):
        """some case we need get parent of node"""
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        item.__parent = node
                        self.visit(item)
            elif isinstance(value, ast.AST):
                value.__parent = node
                self.visit(value)

    @property
    def violations(self):
        return self._result

    def visit_ClassDef(self, node):
        # 使用ast只能检查出继承链最开始的old-style-class，暂未找到方法判断一个类继承了old-style-class
        if not node.bases:
            self._result.append((node, TD005.format(node.name)))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._check_function_default(node)
        self._check_del(node)
        self.generic_visit(node)

    def visit_Call(self, node):
        self._check_return_of_call(node)
        self.generic_visit(node)

    def visit_If(self, node):
        for child in ast.iter_child_nodes(node):
            child.__parent = node

            if child is node.test:
                with self._state.hold_state_ignore_return_check():
                    self.visit(child)
            else:
                # note: 迭代子节点的时候一定是visit，而不是generic_visit
                self.visit(child)

    def visit_Assign(self, node):
        self._check_del_assignment(node)
        with self._state.hold_state_ignore_return_check():
            self.generic_visit(node)

    def visit_Return(self, node):
        with self._state.hold_state_ignore_return_check():
            self.generic_visit(node)

    def visit_UAdd(self, node):
        parent = node.__parent
        if isinstance(parent, ast.UnaryOp) and isinstance(parent.operand, ast.UnaryOp) and\
                isinstance(parent.operand.op, ast.UAdd):
            self._result.append((parent, TD003))
        self.generic_visit(node)

    def visit_USub(self, node):
        parent = node.__parent
        if isinstance(parent, ast.UnaryOp) and isinstance(parent.operand, ast.UnaryOp) and\
                isinstance(parent.operand.op, ast.USub):
            self._result.append((parent, TD003))
        self.generic_visit(node)

    def visit_Str(self, node):
        self._check_str_contain_chinese(node)
        self.generic_visit(node)

    def visit_For(self, node):
        self.generic_visit(node)

    def visit_Name(self, node):
        self.generic_visit(node)

    def _check_function_default(self, func_node):
        for idx, default in enumerate(func_node.args.defaults):
            if isinstance(default, (ast.Dict, ast.List, ast.Set)) or\
                         (isinstance(default, ast.Call) and
                          getattr(default.func, 'id', None) in ("list", "dict", "set")):

                param_name = func_node.args.args[-(idx + 1)].id
                self._result.append((default, TD001.format(func_node.name, param_name)))

            elif isinstance(default, ast.Call):
                param_name = func_node.args.args[-(idx + 1)].id
                self._result.append((default, TD002.format(func_node.name, param_name)))

    def _check_del(self, func_node):
        if func_node.name == '__del__' and isinstance(func_node.__parent, ast.ClassDef):
            self._result.append((func_node, TD004.format(func_node.__parent.name)))

    def _check_del_assignment(self, assign_node):
        names = set(e.id for t in assign_node.targets for e in ast.walk(t) if isinstance(e, ast.Name))
        if '__del__' in names and isinstance(assign_node.__parent, ast.ClassDef):
            self._result.append((assign_node, TD004.format(assign_node.__parent.name)))

    def _check_return_of_call(self, call_node):
        if self._state.ignore_return_check:
            return
        if isinstance(call_node.func, ast.Attribute) and call_node.func.attr in self._checker.return_check_methods:
            self._result.append((call_node, TD006.format(call_node.func.attr, )))

    def _check_str_contain_chinese(self, str_node):
        if not self._checker.forbid_chinese_char:
            return

        # exclude docstring: First expr in (module,class,function) body
        # maybe need exclude assignment?
        if isinstance(str_node.__parent, ast.Expr) and\
                isinstance(str_node.__parent.__parent, (ast.Module, ast.ClassDef, ast.FunctionDef)) and\
                str_node.__parent.__parent.body[0] == str_node.__parent:
            return

        str_value = str_node.s
        if not isinstance(str_value, unicode):
            str_value = str_value.decode('utf-8')
        if any(u'\u4e00' <= uchar <= u'\u9fa5' for uchar in str_value):  # noqa:TD007
            self._result.append((str_node, TD007))


class TrapDetector(object):
    name = 'flake8_trap_detector'
    version = __version__

    def __init__(self, tree, filename):
        self.tree = tree
        self.filename = filename

    def run(self):
        ''' 返回iterater of (line_number, offset, text, check) '''
        visitor = MixedVisitor(self)
        visitor.visit(self.tree)

        for node, reason in visitor.violations:
            yield node.lineno, node.col_offset, reason, type(self)

    @classmethod
    def add_options(cls, parser):
        options.register(
            parser,
            '--return-check-methods', default='', type='string',
            help='Names of the method should be checked return.',
            parse_from_config=True,
            comma_separated_list=True,
        )
        options.register(
            parser,
            '--forbid-chinese-char', default=0, type='int',
            help='whether forbid chinese character in code.',
            parse_from_config=True,
        )

    @classmethod
    def parse_options(cls, parsed_options):
        cls.return_check_methods = set(parsed_options.return_check_methods)
        cls.forbid_chinese_char = parsed_options.forbid_chinese_char
