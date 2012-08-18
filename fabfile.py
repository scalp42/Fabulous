#!/usr/bin/env python

import os
import yaml
import re
import time
import utils
from fabric.api import *
from fabric.contrib import *
from fabric.colors import _wrap_with
from fabric.colors import *

green_bg = _wrap_with('42')

env.application = 'taskrabbit'
env.username = 'deploy'
env.repository = 'git@github.com:runmyerrand/runmyerrand.git'
env.pull_url = 'https://github.com/runmyerrand/runmyerrand/pull'
env.scm = 'git'
env.admin_runner = 'deploy'
env.keep_releases = '5'
env.deploy_via = 'remote_cache'
env.applicationdir = '/home/%(user)s/www/%(application)s' % {'user': env.username, 'application': env.application}
env.deploy_to = env.applicationdir
env.local_dir = '~/taskrabbit/web'
env.macos = local('sw_vers -productVersion', capture=True)

def staging(branch='staging', node='2'):
  env.roledefs = {
    'web': [
      '%(user)s@s-app%(node)s.taskrabbit.net' % {'user': env.username, 'node': node}
    ]
  }
  env.branch = branch
  env.state = 'staging'
  env.node = node

def production(branch='production'):
  env.roledefs = {
    'web': [
      '%(user)s@prod-app8.taskrabbit.net' % {'user': env.username}
    ]
  }
  env.branch = branch
  env.state = 'production'

@roles('web')
def setup_repo():
  """Set up repository / checkout"""
  timestamp = run("date '+%Y%m%d%H%M%S'")
  timestamp_with_dots = timestamp[0:len(timestamp) - 2] + '.' + timestamp[len(timestamp)-2:len(timestamp)]

  sha = local('git ls-remote %(repo)s %(branch)s' % {'repo': env.repository, 'branch': env.branch}, capture=True)
  sha = sha.split("\t")[0]

  cache_dir = '%(app_dir)s/shared/cached-copy' % {'app_dir': env.applicationdir}
  deploy_dir = '%(app_dir)s/releases/%(timestamp)s' % {'app_dir': env.applicationdir, 'timestamp': timestamp}
  geo_lite_file = '%(app_dir)s/shared/config/GeoLiteCity.dat' % {'app_dir': env.applicationdir}

  print green_bg("TEST COLORS")

  print(cyan("Testing colors"))

  warn(yellow("BE CAREFUL BLABLA"))


  if(files.exists(cache_dir)):
    with cd(cache_dir):
      run('git fetch -q origin')
      run('git reset -q --hard %(sha)s' % {'sha': sha})
      run('git clean -q -d -x -f')
  else:
    run('git clone -q %(repo)s %(cache_dir)s' % {'repo': env.repository, 'cache_dir': cache_dir})
    with cd('%(cache_dir)s' % {'cache_dir': cache_dir}):
      run('git checkout -q -b %(user)s %(sha)s;' % {'sha': sha, 'user': env.username})

  with cd(cache_dir):
    run('cp -RPp %(cache_dir)s %(deploy_dir)s' % {'cache_dir': cache_dir, 'deploy_dir': deploy_dir})
    run('echo %(sha)s > %(deploy_dir)s/REVISION' % {'sha': sha, 'deploy_dir': deploy_dir})

  with cd(deploy_dir):
    run('bundle install --gemfile %(deploy_dir)s/Gemfile --path %(app_dir)s/shared/bundle --quiet --without development test cucumber' % {'deploy_dir': deploy_dir, 'app_dir': env.applicationdir})
    run('./script/gem_downgrade_time')

  run('chmod -R g+w %(deploy_dir)s' % {'deploy_dir': deploy_dir})
  run('rm -rf %(deploy_dir)s/log %(deploy_dir)s/public/system %(deploy_dir)s/tmp/pids' % {'deploy_dir': deploy_dir})
  run('mkdir -p %(deploy_dir)s/public' % {'deploy_dir': deploy_dir})
  run('mkdir -p %(deploy_dir)s/tmp' % {'deploy_dir': deploy_dir})
  run('ln -s %(app_dir)s/shared/log %(deploy_dir)s/log' % {'app_dir': env.applicationdir, 'deploy_dir': deploy_dir})
  run('ln -s %(app_dir)s/shared/system %(deploy_dir)s/public/system' % {'app_dir': env.applicationdir, 'deploy_dir': deploy_dir})
  run('ln -s %(app_dir)s/shared/pids %(deploy_dir)s/tmp/pids' % {'app_dir': env.applicationdir, 'deploy_dir': deploy_dir})
  run("find %(deploy_dir)s/public/images %(deploy_dir)s/public/stylesheets %(deploy_dir)s/public/javascripts -exec touch -t %(timestamp_with_dots)s {} ';'; true" % {'deploy_dir': deploy_dir, 'timestamp': timestamp, 'timestamp_with_dots': timestamp_with_dots})

  if(env.state == 'production'):
    with cd(deploy_dir):
      run('bundle exec whenever --clear-crontab %(app_name)s' % {'app_name': env.application})

  if(not files.exists(geo_lite_file)):
    utils.line_break()
    print("ERROR: GeoLiteCity file doesn't exist: %(file)s" % {'file': geo_lite_file})
    utils.line_break()
    return False

  fs = [
    {'file': 'shards-replication.yml', 'final_file': 'shards.yml'},
    {'file': 'database.yml'},
    {'file': 'core.yml'},
    {'file': 'authorize_net.yml'},
    {'file': 'braintree.yml'},
    {'file': 'braintree.yml'},
    {'file': 'google_maps.yml'},
    {'file': 'server.yml'},
    {'file': 's3.yml'},
    {'file': 'GeoLiteCity.dat'},
    {'file': 'unicorn.rb'}
  ]

  for f in fs:
    try:
      final = f['final_file']
    except KeyError:
      final = f['file']
    run('ln -nfs %(app_dir)s/shared/config/%(f)s %(deploy_dir)s/config/%(final)s' % {'f': f['file'], 'final': final, 'app_dir': env.applicationdir, 'deploy_dir': deploy_dir})

  run('ln -nfs %(app_dir)s/shared/cache %(deploy_dir)s/public/cache' % {'app_dir': env.applicationdir, 'deploy_dir': deploy_dir})
  run('ls -x %(app_dir)s/releases' % {'app_dir': env.applicationdir})

  with cd(deploy_dir):
    run('bundle exec rake RAILS_ENV=%(state)s db:migrate compass:compile db:seed 1> /dev/null' % {'state': env.state})
    run('ln -sf %(deploy_dir)s %(app_dir)s/current' % {'deploy_dir': deploy_dir, 'app_dir': env.applicationdir})
    run('bundle exec jammit')
    run('cp public/robots_disallow.txt public/robots.txt')
    run('rm -f %(app_dir)s/current' % {'app_dir': env.applicationdir})
    run('ln -s %(deploy_dir)s %(app_dir)s/current' % {'deploy_dir': deploy_dir, 'app_dir': env.applicationdir})
  
  with cd('%(deploy_dir)s/..' % {'deploy_dir': deploy_dir}):
    to_delete = 5
    dirs = run("ls -ltr | awk '{print $8}'").split('\n')
    total = len(dirs)
    if(total > to_delete):
      del_dirs = dirs[0:total - to_delete]
      for d in del_dirs:
        d = d[0:len(d)-1]
        run('rm -Rf %(dd)s' % {'dd': d})

  with cd('%(app_dir)s/current' % {'app_dir': env.applicationdir}):
    run('bundle exec whenever --update-crontab %(app_name)s --set environment=%(state)s' % {'state': env.state, 'app_name': env.application})

  if(env.state == 'staging'):
    utils.line_break()
    print("Killing unicorns, the bastards...")
    print(red("Killing unicorns, the bastards..."))
    utils.line_break()
    with settings(warn_only=True):
      run('pkill -f unicorn')
      if(files.exists('%(app_dir)s/current/config/unicorn/%(state)s.rb' % {'state': env.state, 'app_dir': env.applicationdir})):
        with cd('%(app_dir)s/current' % {'app_dir': env.applicationdir}):
          run('BUNDLE_GEMFILE=%(app_dir)s/current/Gemfile bundle exec unicorn_rails -c %(app_dir)s/current/config/unicorn/%(state)s.rb -E %(state)s -D' % {'app_dir': env.applicationdir, 'state': env.state})
  elif(env.state == 'production'):
    if(files.exists('%(app_dir)s/current/tmp/pids/unicorn.pid' % {'app_dir': env.applicationdir})):
      print("PRODUCTION UNICORN RELOAD VOILA")

  with cd('%(app_dir)s' % {'app_dir': env.applicationdir}):
    with cd('%(app_dir)s/current' % {'app_dir': env.applicationdir}):
      run('bundle exec rake page_cache:refresher:disable_all cache:clear_rescue cache:clear_storehouse dj:disable dj:stop dj:enable dj:start RAILS_ENV=%(state)s' % {'state': env.state})
      run('rm -fr shared/cache/*')

def deploy():
  """Run the deploy"""
  if(env.state == 'staging' and env.macos == '10.8'):
    local('terminal-notifier -message "Deploying %(branch)s to s-app%(node)s" -title "Fabric"' % {'branch' : env.branch, 'node': env.node})
    #local('say -v Vicki "Deployment to s-app%(node)s started. Hang tight."' % {'node': env.node})
  execute(setup_repo)
  if(env.state == 'staging' and env.macos == '10.8'):
    local('terminal-notifier -message "Deployed %(branch)s to s-app%(node)s !" -title "Fabric" -subtitle "DONE"' % {'branch' : env.branch, 'node': env.node})
    #local('say -v Vicki "Deployment to s-app%(node)s is finished. Have fun."' % {'node': env.node})

if __name__ == '__main__':
  execute(deploy)