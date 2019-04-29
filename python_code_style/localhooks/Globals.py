#coding: utf-8


logger = None # 全局logger

class CHECK_STATUS:
    PASS = 2 # 未发现错误
    CONTINUE = 1 # 发现错误继续检查
    STOP = 0 # 发现错误停止检查