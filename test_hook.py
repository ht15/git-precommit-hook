# -*- coding: UTF-8 -*-
import subprocess
ini_path = '/home/ht/precommit_hook/git-precommit-hook/python_code_style/tox.ini'
print ini_path
filename ='/home/ht/precommit_hook/git-precommit-hook/test.py'
print filename
tox_working_path = '/home/ht/precommit_hook/git-precommit-hook/python_code_style/'
print tox_working_path
args = ['python', '-m', 'flake8', '--config', ini_path, filename]
p = subprocess.Popen('python -m flake8 --config=%s %s' % (ini_path, filename), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell = True, cwd = tox_working_path)
stdout, stderr = p.communicate()
print stdout, stderr
