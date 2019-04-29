# -*- coding:utf-8 -*-
import sys, urllib, urllib2, json, time, os
from file_exclude import check_server_file_exlucde, check_client_file_exlucde

reload(sys)
sys.setdefaultencoding('utf-8')
# 代码检查webhook链接
CODE_LINT_URL = 'http://10.246.46.108:10020/code-lint'

def get_change_list(change_list_file):
    l = []
    try:
        change_list = open(change_list_file, 'rt').readlines()
        for s in change_list:
            action, path_name = s.split(' ', 1)
            path_name = path_name.strip()
            l.append([action, path_name])
    except:
        pass
    return l


# 判断是否需要获取提交内容，过滤方法，只获取文本文件，建议以文件后缀过滤
def is_get_code_lint_content(change_file):
    if not change_file.endswith('.py'):
        return False
    if is_server_file(change_file) or is_client_file(change_file):
        return True
    return False

def is_server_file(change_file):
    try:
        engine_idx = change_file.index('engine')
    except ValueError:
        return False
    rel_server_path = change_file[engine_idx:]
    return not check_server_file_exlucde(rel_server_path)

def is_client_file(change_file):
    try:
        script_idx = change_file.index('script')
    except ValueError:
        return False
    rel_client_path = change_file[script_idx:]
    return not check_client_file_exlucde(rel_client_path)    

def get_repo_path():
    return os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

def get_file_content(change_list, txn):
    change_list = json.loads(change_list)
    repo_path = get_repo_path()
    change_list = [c[1] for c in change_list]
    files_content = []
    for change_file in change_list:
        if not is_get_code_lint_content(change_file):
            continue
        content = os.popen('svnlook cat ' + repo_path + ' ' + change_file + ' -t ' + txn).readlines()
        file_content = {
            'file': change_file,
            'content': content
        }
        files_content.append(file_content)
    return files_content


def pre_commit(repos, txn, author, log_file, change_list_file, pre_commit_url):
    """ pre-commit http request """
    change_list = get_change_list(change_list_file)
    change_list = json.dumps(change_list)


    log = ''.join( open(log_file, 'r').readlines() )

    d = {
        'token': repos,
        'txn': txn,
        'author': author,
        'log': log,
        'change_list': change_list
    }

    d = urllib.urlencode(d)  # encode parameters
    req = urllib2.Request(pre_commit_url + '?r=%s' % time.time(), data=d)
    try:
        r = urllib2.urlopen(req, timeout=60)
        r = r.read()
        r = json.loads(r)
        # 代码通过svnci检查，下面检查代码内容，向lint-code发起验证，发送author，log，files_content信息，建议设置timeout
        if r['code'] == 0:
            files_content = get_file_content(change_list, txn)
            d = {
                'author': author,
                'log': log,
                'files_content': json.dumps(files_content)
            }
            d = urllib.urlencode(d)
            req = urllib2.Request(CODE_LINT_URL + '?r=%s' % time.time(), data=d)
            try:
                r = urllib2.urlopen(req, timeout=60)
                r = r.read()
                r = json.loads(r)
                if r['code'] == 0:
                    return 0
                sys.stderr.write('---------------------[LINT CODE ERROR]--------------------\n')
                sys.stderr.write(r['msg'].encode('utf-8') + '\n')
                sys.stderr.write('\n---------------------[LINT CODE ERROR]--------------------\n')
                return r['code']
            except Exception, e:
                return 0


        sys.stderr.write('---------------------[SVN-ci ERROR]--------------------\n')
        sys.stderr.write('\nPermission denied, the reason below, see detail on SVN-ci.\n')
        sys.stderr.write(r['msg'].encode('utf-8') + '\n')
        sys.stderr.write('\n---------------------[SVN-ci ERROR]--------------------\n')

        return r['code']  # error, return error msg
    except Exception, e:
        return 0  # if network error or server error, allow to commit.


def post_commit(repos, rev, author, log_file, change_list_file, post_commit_url):
    """ post commit http requests """
    change_list = get_change_list(change_list_file)
    change_list = json.dumps(change_list)
    
    log = ''.join( open(log_file, 'r').readlines() )

    d = {
        'token': repos,
        'rev': rev,
        'author': author,
        'log': log,
        'change_list': change_list
    }
    d = urllib.urlencode(d)  # encode parameters
    req = urllib2.Request(post_commit_url + '?r=%s' % time.time(), data=d)
    try:
        urllib2.urlopen(req)  # no need to get the result
    except:
        pass
    return '0'  # pass


if __name__ == '__main__':
    argv = sys.argv
    if len(argv) == 8:
        hook = argv[1]
        if hook == 'pre_commit':
            # need the return value
            sys.exit(pre_commit(*argv[2:]))
        elif hook == 'post_commit':
            sys.exit(post_commit(*argv[2:]))
    sys.exit(0)  # allow commit
