# -*- coding: utf-8 -*-

from ncm2 import Ncm2Source, getLogger, Popen
import subprocess
import re
from os.path import dirname
from os import path
from ncm2_libclang import args_from_cmake, args_from_clang_complete
import vim
import json
import time

logger = getLogger(__name__)


class Source(Ncm2Source):

    def __init__(self, nvim):
        Ncm2Source.__init__(self, nvim)

        this_file = path.abspath(__file__)
        basedir = path.dirname(this_file)
        basedir = path.dirname(basedir)

        ncm_libclang_bin = nvim.vars['ncm2_libclang#bin']
        if type(ncm_libclang_bin) == str:
            ncm_libclang_bin = [ncm_libclang_bin]

        ncm_libclang_bin[0] = path.join(basedir, ncm_libclang_bin[0])

        if not path.isfile(ncm_libclang_bin[0]):
            raise Exception("%s doesn't exist, please compile it" %
                            ncm_libclang_bin[0])

        self.proc = Popen(args=ncm_libclang_bin,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)

        nvim.command(
            "call ncm2_libclang#on_warmup(ncm2#context())", async_=True)

    def get_args_dir(self, ncm2_ctx, data):
        filepath = ncm2_ctx['filepath']

        cwd = data['cwd']
        database_path = data['database_path']

        args = []
        run_dir = cwd
        cmake_args, directory = args_from_cmake(filepath, cwd, database_path)
        if cmake_args is not None:
            args = cmake_args
            run_dir = directory
        else:
            clang_complete_args, directory = args_from_clang_complete(
                filepath, cwd)
            if clang_complete_args:
                args = clang_complete_args
                run_dir = directory

        return args, run_dir

    def cache_add(self, ncm2_ctx, lines, data):
        src = self.get_src("\n".join(lines), ncm2_ctx)

        args, directory = self.get_args_dir(ncm2_ctx, data)

        start = time.time()

        req = {}
        req['command'] = 'cache_add'
        req['filepath'] = ncm2_ctx['filepath']
        req['args'] = args
        req['directory'] = directory
        req['src'] = src

        if ncm2_ctx['filetype'] == 'cpp':
            req['lang'] = 'c++'
        else:
            req['lang'] = 'c'

        req = json.dumps(req) + "\n"

        logger.debug('req: %s', req)

        self.proc.stdin.write(req.encode())
        self.proc.stdin.flush()

        rsp = self.proc.stdout.readline()
        rsp = json.loads(rsp.decode())

        end = time.time()

        logger.debug("cache_file time: %s, rsp: [%s]", end - start, rsp)

    def on_complete(self, ncm2_ctx, lines, data):
        src = self.get_src("\n".join(lines), ncm2_ctx)

        filepath = ncm2_ctx['filepath']
        startccol = ncm2_ctx['startccol']

        cwd = data['cwd']
        database_path = data['database_path']

        args, directory = self.get_args_dir(ncm2_ctx, data)

        start = time.time()

        req = {}
        req["command"] = "code_completion"
        req['filepath'] = filepath
        req['args'] = args
        req['src'] = src
        req['lnum'] = ncm2_ctx['lnum']
        req['bcol'] = ncm2_ctx['bcol']
        req['directory'] = directory

        if ncm2_ctx['scope'] == 'cpp':
            req['lang'] = 'c++'
        else:
            req['lang'] = 'c'

        req = json.dumps(req) + "\n"

        logger.debug("req: %s", req)

        self.proc.stdin.write(req.encode())
        self.proc.stdin.flush()

        rsp = self.proc.stdout.readline()
        rsp = json.loads(rsp.decode())

        end = time.time()

        logger.debug("code_completion time: %s, rsp: [%s]", end - start, rsp)

        matches = rsp["matches"]
        self.complete(ncm2_ctx, startccol, matches)


source = Source(vim)

on_complete = source.on_complete
cache_add = source.cache_add
