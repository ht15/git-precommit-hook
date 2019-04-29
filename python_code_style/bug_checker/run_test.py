# -*- coding:utf-8 -*-
import ast
import unittest
from trap_detector import TrapDetector


class DummyOption(object):
    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])


class TestTrapDetector(unittest.TestCase):
    def _assert_validations(self, code, error_codes):
        tree = ast.parse(code)
        checker = TrapDetector(tree, '')
        self.assertEqual([c[2].split()[0] for c in checker.run()], error_codes)

    def setUp(self):
        opt = DummyOption(return_check_methods=('check_ret_of_me', ),
                          forbid_chinese_char=1)
        TrapDetector.parse_options(opt)

    def test_TD001(self):
        code = """
class OBJ(object):
    def f(self, a=list()):
        pass

def test(a, k={}):
    list = a
    print list
        """
        self._assert_validations(code, ['TD001', 'TD001'])

    def test_TD002(self):
        code = """
import random
import time
def test_default(a=random.ramdom()):
    def test_default_in(t=time.time()):
        print a, t, time.time()
    test_default_in()

        """
        self._assert_validations(code, ['TD002', 'TD002'])

    def test_TD003(self):
        code = """
def test_return(a, b):
    ++a
    --b
        """
        self._assert_validations(code, ['TD003', 'TD003'])

    def test_TD004(self):
        code = """
class OBJ1(object):
    def __del__(self):
        pass

class OBJ2(object):
    def destroy(self):
        pass
    __del__ = destroy

def __del__():
    pass
        """
        self._assert_validations(code, ['TD004', 'TD004'])

    def test_TD005(self):
        code = """
class OBJ1:
    pass

class OBJ2():
    pass

class OBJ3(OBJ1):
    pass
        """
        self._assert_validations(code, ['TD005', 'TD005'])

    def test_TD006(self):
        code = """
def test_return(self):
    self.check_ret_of_me()

self.check_ret_of_me()
        """
        self._assert_validations(code, ['TD006', 'TD006'])

    def test_TD006_no_error(self):
        code = """
def test_return(self):
    if self.check_ret_of_me() and self.sth:
        check_ret_of_me()  # just check method

    a = self.check_ret_of_me()
    a, b = self.check_ret_of_me(), 1
    if b:
        return self.check_ret_of_me()
    return a, self.check_ret_of_me()
        """
        self._assert_validations(code, [])

    def test_TD007(self):
        code = """
def test_chinese():
    s = '中文'
    if s == 'may英文':  # TODO(LMS) test will fail with u'英文'
        s = 'english'
        """
        # tree = ast.parse(code)
        # checker = MultiBugChecker(tree, '')
        # print list(checker.run()), ast.dump(tree)
        self._assert_validations(code, ['TD007', 'TD007'])

    def test_TD007_no_error(self):
        code = """
'''docstring不包含在检查范围内'''
class OBJ(object):
    '''docstring不包含在检查范围内'''
    def test():
        '''docstring不包含在检查范围内'''
        pass
        """
        self._assert_validations(code, [])


if __name__ == '__main__':
    unittest.main()
