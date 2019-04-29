#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@version: v1.0
@author: caiminchao
@corp: caiminchao@corp.netease.com
@software: PyCharm，python 2.7
@file: pre_param
@time: 2018/9/21 15:21
@description:svn hook of linux os
"""
import subprocess, sys, os, logging
from logging.config import dictConfig
import Globals as g
import const, checkPath
import platform, locale

from hmac import HMAC
from hashlib import md5

reload(sys)
sys.setdefaultencoding('utf8')

if not platform.system() == 'Windows':
	language_code, encoding = locale.getdefaultlocale()
	if language_code is None:
		language_code = 'en_GB'
	if encoding is None:
		encoding = 'UTF-8'
	if encoding.lower() == 'utf':
		encoding = 'UTF-8'
	locale.setlocale(locale.LC_ALL, '%s.%s' % (language_code, encoding))


def initLogger(pre_commit_work_path):
	log_path = os.path.join(os.path.split(pre_commit_work_path)[0], 'pre-commit.log')
	logging_config = dict(
		version=1,
		formatters={
			'f': {
				'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
				'datefmt': '%Y-%m-%d %H:%M:%S'
			}
		},
		handlers={
			'h': {
				'class': 'logging.FileHandler',
				'formatter': 'f',
				'level': logging.DEBUG,
				'filename': log_path,
				'mode': 'w+',
				'encoding': 'utf-8',
			}
		},
		root={
			'handlers': ['h'],
			'level': logging.DEBUG,
		},
	)
	dictConfig(logging_config)
	g.logger = logging.getLogger()


def save_res_ret(file_path, msg):
	res_file = open(file_path, 'w')
	res_file.write(msg)
	res_file.close()


def get_change_list(diff_list_file, abs_file):
	change_list = open(diff_list_file, 'rt').readlines()
	root_path = open(abs_file, 'rt').readline().strip('\n')
	l = []
	for s in change_list:
		path_name = (root_path + '/' + s.strip()).strip()
		l.append(path_name)

	return l


def run_precommit(diff_list_file, res_file, localRoot, abs_file, posi_file):
	change_list = get_change_list(diff_list_file, abs_file)
	localProjectRoot = sys.argv[0]
	initLogger(localProjectRoot)
	precommit = PreCommit(change_list, localRoot, localProjectRoot)

	pre_ret = precommit.check()
	save_res_ret(res_file, pre_ret)
	if precommit.logPosi:
		save_res_ret(posi_file, '|' + precommit.logPosi)
	return 0 if pre_ret == 'pass' else 1


class PreCommit(object):
	def __init__(self, changelist, localRoot, localProjectRoot):
		self.changelist = changelist
		self.localRoot = localRoot
		self.localProjectRoot = localProjectRoot
		g.logger.info('changelist:' + str(changelist))
		g.logger.info('localRoot:' + localRoot)
		g.logger.info('projectRoot:' + localProjectRoot)
		# self.svnRoot = self.getSvnUrl(localRoot)
		self.logPosi = None
		self.initStaticCheck()

	# def getSvnUrl(self, localRoot):
	# 	return pysvn.Client().info(localRoot).url

	def check(self):
		if not self.needCheckScript:
			return 'pass'
		else:
			return self.checkStatic()

	# static code check
	def initStaticCheck(self):
		g.logger.info('changelist:' + str(self.changelist) + '\n')
		# scriptSpliter = ['/client/script/', '/server/res/entities/']
		self.svnScriptPath = None
		self.localScriptPath = None
		self.needCheckScript = False
		for localPath in self.changelist:
			# svnPath = '%s/%s' % (self.svnRoot, localPath[len(self.localRoot) + 1:].replace('\\', '/'))
			for sp in checkPath.checkPath:
				# 防止程序配置检查路径错误增加的后缀判断
				if localPath.startswith(sp):
					if sp.endswith('client/script/') or sp.endswith('res/entities/'):
						self.needCheckScript = True
						break

	def checkStatic(self):
		g.logger.info('checkStatic start:\n')
		check_result = ''
		for c in self.changelist:
			for sp in checkPath.checkPath:
				if len(c.split(sp)) > 1:
					script_path = c.split(sp)[-1]
					if c.startswith(sp):
						if c.endswith('.py'):
							if os.path.exists(c):
								if not script_path in const.whiteList:
									g.logger.info('checkUrl:' + c + '\n')
									path = self.localProjectRoot.replace('\\', '/').replace('pre_param.py',
																							'flake8.conf')
									p = subprocess.Popen(['flake8', '--config', path, c], stdout=subprocess.PIPE,
														 stderr=subprocess.PIPE, shell=False)
									stdout, stderr = p.communicate()
									if stderr:
										g.logger.error('[error]Analysing file: %s  is error!!!' % c)
										g.logger.error(stderr + '\n')
										check_result = 'please contact caiminchao@corp.netease.com: Linux-client-side pre-hook error!\n'
										break
									else:
										#  collect result
										if stdout:
											g.logger.info('stdout:\n' + stdout)
											check_result_list = stdout.replace(c, '').split('\n')[:-1]
											for res in check_result_list:
												check_result = check_result + c + ':' + res + '\n'

		g.logger.info('result:\n' + check_result)
		if check_result != '':
			check_result = '[svn client hook]STATIC CODE REVIEW is not passed,Please Check and Modify:\n' + check_result
			return check_result
		else:
			sortedChangeListStr = ''.join(sorted(self.changelist))
			salt = 'de60e4dc78011991'
			self.logPosi = HMAC(str(sortedChangeListStr), salt, md5).hexdigest().strip()
			g.logger.info('MD5: ' + self.logPosi)
			return 'pass'


if __name__ == '__main__':
	flag = True
	if flag:
		argv = sys.argv
		hook = argv[1]
		if hook == 'run_precommit' and len(argv) == 7:
			sys.exit(run_precommit(*argv[2:]))
	else:
		pass
