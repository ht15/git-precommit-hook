#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import sys, os, logging
from logging.config import dictConfig
import Globals as g
import const, checkPath

from hmac import HMAC
from hashlib import md5

sys.path.append(os.path.dirname( os.path.dirname( os.path.abspath(__file__) ) ))
from file_exclude import check_client_file_exlucde
from file_exclude import check_server_file_exlucde
from tempfile import mkstemp
from os import fdopen
from shutil import move
import platform

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

	def __init__(self, changelist, localProjectRoot):
		self.changelist = changelist
		self.localProjectRoot = localProjectRoot
		self.initStaticCheck()

	def check(self):
		return (not self.needCheckScript or self.checkStatic()) and self.pass_special_mask_field

	def initStaticCheck(self):
		g.logger.info('changelist:' + str(self.changelist) + '\r\n')
		self.needCheckScript = False
		self.pass_special_mask_field = True

		if not self._filter_special_mask_field():
			self.pass_special_mask_field = False
			return
		self.changelist = self._filter_changelist_by_special_files(self.changelist)
		if not const.is_windows:
			self.changelist = self._change_to_dest_path(self.changelist)

		for localPath in self.changelist:
			for sp in checkPath.checkPath:
				if localPath.startswith(sp):
					self .needCheckScript = True
					break

	def _change_to_dest_path(self, changelist):
		ret = []
		path_dir = self.localProjectRoot[0:self.localProjectRoot.find('.git')]
		for filename in changelist:
			ret.append(path_dir + filename)
		return ret

	def _filter_special_mask_field(self):
		check_result = ''
		for localPath in self.changelist:
			if not os.path.exists(localPath) or os.path.isdir(localPath):
				continue
			with open(localPath, 'r') as f:
				for num, line in enumerate(f):
					for key in self.MASK_FIELD:
						if not localPath.endswith('pre_commit.py') and key in line:
							check_result = check_result + key + ' in ' + localPath + ', line_no: ' + str(num) + '\n'
		if check_result != '':
			g.logger.error('result:\r\n' + check_result)
			sys.stderr.write(
				'[svn client hook]STATIC CODE REVIEW is not passed, becase these file include special mask field ,Please Check and Modify:\n' + check_result)
			return False
		return True

	def _filter_changelist_by_special_files(self, changelist):
		ret = []
		for filename in changelist:
			if self._filter_changelist_by_special_client_files(filename):
				g.logger.info(filename + ' exist in old client files')
				continue
			elif self._filter_changelist_by_special_server_files(filename):
				g.logger.info(filename + ' exist in old server files')
				continue
			ret.append(filename)
		return ret

	def _filter_changelist_by_special_client_files(self, filename):
		index = filename.find('/script/')
		if index != -1:
			source_filename = filename[index + 1:]
			des_filename = source_filename.replace('/', '\\')
			return check_client_file_exlucde(des_filename) # des_filename in set([r"script\ui\social_ui\FriendViewController.py,"])
		return False

	def _filter_changelist_by_special_server_files(self, filename):
		index = filename.find('/engine/')
		if index != -1:
			source_filename = filename[index + 1:]
			des_filename = source_filename.replace('/', '\\')
			return check_server_file_exlucde(des_filename)
		return False

	def _check_single_file_valid(self, file, check_file):
		if const.is_windows:
			if not file.startswith(check_file) or not file.endswith('.py') or len(file.split(check_file)) <= 1:
				return False
		else:
			if not file.endswith('.py'):
				return False
		if not os.path.exists(file):
			return False
		if file in const.whiteList:
			return False
		return True

	def _do_check_single_file(self, file):
		check_result = ''
		for sp in checkPath.checkPath:
			if not self._check_single_file_valid(file, sp):
				continue
			g.logger.info('checkUrl:' + file + '\r\n')
			ini_path = self.localProjectRoot.replace('\\', '/').replace('localhooks/pre_commit.py', 'tox.ini')
			tox_working_path = self.localProjectRoot[0: self.localProjectRoot.find('localhooks')]
			p = subprocess.Popen('python -m flake8 --config=%s %s' % (ini_path, file), stdout=subprocess.PIPE,
								 stderr=subprocess.PIPE, shell=True, cwd=tox_working_path)
			stdout, stderr = p.communicate()
			if stderr:
				g.logger.error('[error]Analysing file: %s  is error!!!\r\n' % file)
				g.logger.error(stderr.decode('gbk') + '\r\n')
				sys.stderr.write('please contact huangtao3@corp.netease.com: client-side pre-hook error! \r\n')
				return False, check_result
			check_result_list = stdout.replace(file, '').split('\n')[:-1]
			for res in check_result_list:
				check_result = check_result + file + ':' + res + '\n'
			return True, check_result
		return  True, check_result


	def checkStatic(self):
		g.logger.info('checkStatic start:\r\n')
		st = True
		check_result = ''
		for file in self.changelist:
			ret, check_info = self._do_check_single_file(file)
			if not ret:
				return ret
			check_result = check_result + check_info

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
		return st


if __name__ == '__main__':
	flag = True
	if flag:
		initLogger(sys.argv[0])
		g.logger.info(str(sys.argv) + '\r\n')
		g.logger.info(platform.system())
		if 'Window' in platform.system():
			const.is_windows = True
		else:
			const.is_windows = False
		if const.is_windows:
			changelist = getContentFromFile(sys.argv[1]).splitlines()
		else:
			changelist = sys.argv[1:]
		localProjectRoot = sys.argv[0]
		precommit = PreCommit(changelist, localProjectRoot)
		sys.exit(0 if precommit.check() else 1)
	else:
		pass
