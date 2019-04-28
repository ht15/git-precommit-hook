#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import sys, os, platform, logging
from logging.config import dictConfig
import Globals as g
import const, checkPath

from hmac import HMAC
from hashlib import md5

from asset_check.asset_check import AssetCheck
from asset_check.path_helper import PathHelper

sys.path.append(os.path.dirname( os.path.dirname( os.path.abspath(__file__) ) ))
from file_exclude import check_client_file_exlucde
from file_exclude import check_server_file_exlucde
from tempfile import mkstemp
from os import fdopen
from shutil import move

pysvn = __import__('pysvn%s' % (platform.architecture()[0][:2]))

reload(sys)
sys.setdefaultencoding('utf8')


def initLogger(pre_commit_work_path):
	# 配置logger
	log_path = os.path.split(pre_commit_work_path)[0] + '/pre-commit.log'
	try:
		if not os.path.exists(log_path):
			file_object = open(log_path, 'w')
			file_object.close()
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
	except Exception, e:
		fh, abs_path = mkstemp()
		with fdopen(fh, 'w') as new_file:
			new_file.write(str(e))
		move(abs_path, log_path)


def getContentFromFile(filename):
	assert os.path.exists(filename), 'file not exists:%s' % filename
	with open(filename, 'r') as f:
		content = f.read()
	return content


class PreCommit(object):
	MASK_FIELD = ['pydevd', 'PycharmDebug']

	def __init__(self, changelist, localRoot, localProjectRoot):
		self.md5Flag=False
		self.changelist = changelist
		self.localRoot = localRoot
		self.localProjectRoot = localProjectRoot
		# self.svnRoot = self.getSvnUrl(localRoot)
		self.initStaticCheck()

	# self.initResInfo()

	def initResInfo(self):
		resSpliter = '/client/res/'
		g.logger.info(self.changelist + '\r\n')
		self.changelistDict = {}
		for localPath in self.changelist:  # 只要检测到有需要check，就break
			svnPath = '%s/%s' % (self.svnRoot, localPath[len(self.localRoot) + 1:].replace('\\', '/'))
			if resSpliter in svnPath:
				self.svnResPath = '%s%s' % (svnPath.split(resSpliter, 1)[0], resSpliter)
				self.localResPath = '%s%s' % (localPath.split(resSpliter, 1)[0], resSpliter)
				self.needCheckAssets = True
				break
		else:
			self.svnResPath = None
			self.localResPath = None
			self.needCheckAssets = False

	def getSvnUrl(self, localRoot):
		return pysvn.Client().info(localRoot.decode('gbk')).url

	def check(self):
		return (not self.needCheckScript or self.checkStatic()) and self.pass_special_mask_field

	# return not self.needCheckAssets or self.checkAssets()

	def checkAssets(self):
		pathHelper = PathHelper(self.localResPath, self.svnResPath, self.changelist)
		st = True
		for c in self.changelist:
			ac = AssetCheck(c, pathHelper)
			for item in ac.check():
				st = False
				sys.stderr.write('CANNOT PASS ASSETCHECK\n%s\n%s\n\n' % (item['file'], item['message'].encode('gbk')))

		return st

	# static code check
	def initStaticCheck(self):
		g.logger.info('changelist:' + str(self.changelist) + '\r\n')
		# scriptSpliter = ['/client/script/', '/server/res/entities/']
		self.svnScriptPath = None
		self.localScriptPath = None
		self.needCheckScript = False
		self.pass_special_mask_field = True

		if not self._filter_special_mask_field():
			self.pass_special_mask_field = False
			return
		self.changelist = self._filter_changelist_by_special_files(self.changelist)

		for localPath in self.changelist:
			g.logger.info('localPath: ' + localPath)
			# svnPath = '%s/%s' % (self.svnRoot, localPath.decode('gbk')[len(self.localRoot) + 1:].replace('\\', '/'))
			for sp in checkPath.checkPath:
				# 防止程序配置检查路径错误增加的后缀判断
				if localPath.startswith(sp):
					self.needCheckScript = True
					g.logger.info('special path: ' + sp + ', needCheckScript :' + 'True')
					break

	def _filter_special_mask_field(self):
		check_result = ''
		for localPath in self.changelist:
			if not os.path.exists(localPath) or os.path.isdir(localPath):
				continue
			with open(localPath, 'r') as f:
				for num, line in enumerate(f):
					for key in self.MASK_FIELD:
						if key in line and localPath != 'E:/H48/code/programer_tools/python_code_style/localhooks/pre_commit.py':
							check_result = check_result + key + ' in ' + localPath + ', line_no: ' + str(num) + '\n'
		if check_result != '':
			sys.stderr.write(
				'[svn client hook]STATIC CODE REVIEW is not passed, becase these file include special mask field ,Please Check and Modify:\n' + check_result)
			return False
		return True

	def _filter_changelist_by_special_files(self, changelist):
		ret = []
		for filename in changelist:
			if self._filter_changelist_by_special_client_files(filename):
				g.logger.info(filename + ' exist in ')
				continue
			elif self._filter_changelist_by_special_server_files(filename):
				g.logger.info(filename + ' exist in ')
				continue
			ret.append(filename)
		return ret

	def _filter_changelist_by_special_client_files(self, filename):
		index = filename.find('/script/')
		g.logger.info('_filter_changelist_by_special_client_files index :' + str(index))
		if index != -1:
			source_filename = filename[index + 1:]
			des_filename = source_filename.replace('/', '\\')
			g.logger.info(des_filename)
			return check_client_file_exlucde(des_filename) # des_filename in set([r"script\ui\social_ui\FriendViewController.py,"])
		return False

	def _filter_changelist_by_special_server_files(self, filename):
		index = filename.find('/engine/')
		g.logger.info('_filter_changelist_by_special_server_files index :' + str(index))
		if index != -1:
			source_filename = filename[index + 1:]
			des_filename = source_filename.replace('/', '\\')
			g.logger.info(des_filename)
			return check_server_file_exlucde(des_filename)
		return False

	def checkStatic(self):
		g.logger.info('checkStatic start:\r\n')
		pathHelper = PathHelper(self.localScriptPath, self.svnScriptPath, self.changelist)
		st = True
		check_result = ''
		# scriptSpliter = ['/client/script/','/server/res/entities/']
		for c in self.changelist:
			for sp in checkPath.checkPath:
				if len(c.split(sp)) > 1:
					script_path = c.split(sp)[-1]
					g.logger.info('script_path:' + script_path + '\r\n')
					if c.startswith(sp):
						if c.endswith('.py'):
							if pathHelper.existInLocal(c):
								if not script_path in const.whiteList:
									g.logger.info('checkUrl:' + c + '\r\n')
									path = self.localProjectRoot.replace('\\', '/').replace('localhooks/pre_commit.py',
																							'tox.ini')
									tox_path = self.localProjectRoot[0: self.localProjectRoot.find('localhooks')]
									p = subprocess.Popen(['python', '-m', 'flake8', '--config', path, c], stdout=subprocess.PIPE,
														 stderr=subprocess.PIPE, shell=True, cwd=tox_path)
									stdout, stderr = p.communicate()
									if stderr:
										g.logger.error('[error]Analysing file: %s  is error!!!\r\n' % c)
										g.logger.error(stderr.decode('gbk') + '\r\n')
										st = False
										sys.stderr.write(
											'please contact huangtao3@corp.netease.com: client-side pre-hook error! \r\n')
										break
									else:
										#  collect result
										if stdout:
											g.logger.info('stdout:\r\n' + stdout)
											check_result_list = stdout.replace(c, '').split('\n')[:-1]
											for res in check_result_list:
												check_result = check_result + c + ':' + res + '\n'

		g.logger.info('result:\r\n' + check_result)
		if check_result != '':
			sys.stderr.write(
				'[svn client hook]STATIC CODE REVIEW is not passed,Please Check and Modify:\n' + check_result)
			st = False
		else:
			sortedChangeListStr = ''.join(sorted(self.changelist))
			salt = 'de60e4dc78011991'
			logPosi = HMAC(str(sortedChangeListStr), salt, md5).hexdigest().strip()
			if getContentFromFile(sys.argv[3]):
				msg = getContentFromFile(sys.argv[3]) + '|' + logPosi
				g.logger.info('LogMessage: ' + msg)
				# f = open(sys.argv[3], 'w')
				# f.write(msg)
				# f.close()

		return st


if __name__ == '__main__':
	flag = True
	if flag:
		initLogger(sys.argv[0])
		g.logger.info(str(sys.argv) + '\r\n')
		changelist = getContentFromFile(sys.argv[1]).splitlines()
		localRoot = sys.argv[4]
		localProjectRoot = sys.argv[0]
		precommit = PreCommit(changelist, localRoot, localProjectRoot)
		sys.exit(0 if precommit.check() else 1)
	else:
		pass
