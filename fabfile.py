#!/usr/bin/env python

import os
import yaml
import re
import time
import utils
from fabric.api import *
from fabric.contrib import *

env.application = 'taskrabbit'
env.user = 'deploy'
env.repository = 'git@github.com:runmyerrand/runmyerrand.git'
env.pull_url = 'https://github.com/runmyerrand/runmyerrand/pull'
env.scm = 'git'
env.admin_runner = 'deploy'
env.keep_releases = '5'
env.deploy_via = 'remote_cache'
env.applicationdir = "/home/#{user}/www/#{application}"
env.deploy_to = env.applicationdir

def staging(branch='staging', node='1'):
  env.roledefs = {
    'web' : [
      'deploy@s-app%(node)s.taskrabbit.net' % {'node': node}
    ]
  }

def production(branch='production'):
  env.roledefs = {
    'web' : [
      'deploy@prod-app8.taskrabbit.net'
    ]
  }

def test():
  print(env.roledefs['web'])