import os
import yaml
import re
import time
#from fabric.api import run, env, put, open_shell, prompt
from fabric import utils
from fabric.api import *
from fabric.contrib.files import exists, upload_template
from fabric.contrib.console import confirm
from fabric.operations import sudo
from time import sleep

from fabric.contrib import files, console

env.hosts = ['prod-riak00', 'prod-riak01', 'prod-riak02', 'prod-riak03', 'prod-riak04']

env.use_ssh_config = True

env.warn_only = 1

env.output_prefix = 1

time = time.strftime('%Y%m%d-%H%M')

NRPE_VERSION = "2.13"

NAGIOS_PLUGINS_VERSION = "1.4.16"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SKELETON_DIR = os.path.join(CURRENT_DIR, 'skeleton')
SKELETON_DIR_TMP = '/tmp'



# def copy_skeleton_to_path(src_dir, dest_dir, file_name, substitutions):
# 	src = os.path.join(src_dir, file_name)
# 	dest = os.path.join(dest_dir, file_name)

# def substitute_text(key, val, text):
# 	return re.sub("!%s!" % key, val, text)
# 	with open(dest, 'w') as f:
# 		skel = open(src, 'r')
# 		skel_txt = skel.read()
# 		for key, val in substitutions.items():
# 			skel_txt = substitute_text(key, val, skel_txt)
# 			f.write(skel_txt)
# 			skel.close()
# 	copy_skeleton_to_path(SKELETON_DIR, env.nrpe_cfg_location, 'nrpe.cfg', file_var_replacements)


def copy_skeleton_to_path(src_dir, dest_dir, file_name, substitutions):
	src = os.path.join(src_dir, file_name)
	dest = os.path.join(dest_dir, file_name)
	def substitute_text(key, val, text):
		return re.sub("!%s!" % key, val, text)
	with open(dest, 'w') as f:
		skel = open(src, 'r')
		skel_dest = skel.read()
		for key, val in substitutions.items():
			skel_dest = substitute_text(key, val, skel_dest)
		f.write(skel_dest)
		f.close()	
		skel.close()


NRPE_LINK = "http://downloads.sourceforge.net/project/nagios/nrpe-2.x/nrpe-%(ver)s/nrpe-%(ver)s.tar.gz" % {'ver': NRPE_VERSION}

NAGIOS_PLUGINS_LINK = "http://downloads.sourceforge.net/project/nagiosplug/nagiosplug/%(ver)s/nagios-plugins-%(ver)s.tar.gz" % {'ver': NAGIOS_PLUGINS_VERSION}

PACKAGES_UBUNTU = (
			'wget', 'libssl-dev', 'openssl-blacklist', 'openssl-blacklist-extra',
			'python-software-properties',
			'postgresql-client-9.1',
			'xinetd', 'libbind9-60', 'libdns66', 'libisc60', 'libisccc60', 'libisccfg60', 'liblwres60', 'libradius1', 'qstat',
			'radiusclient1', 'snmp', 'snmpd',
			'fping', 'libnet-snmp-perl', 'libldap-dev', 'libmysqlclient-dev', 'libgnutls-dev', 'libradiusclient-ng-dev',
			'libgd2-noxpm-dev', 'libpng12-dev', 'libjpeg62', 'libjpeg62-dev'
			)

PACKAGES_SOLARIS = (
			'nano', 'scmgit', 'automake', 'pkg-config', 'gmake', 'makedepend', 'cmake', 'gettext-m4', 'readline', 'tmux', 'pkg_install-info',
			'm4', 'gtar-base', 'gnutls', 'gawk', 'binutils', 'bison', 'tcp_wrappers', 'mysql-client-5.5*', 'gcc-compiler-4.6.1', 'gcc-compiler',
			'gcc-runtime', 'nano', 'zip', 'unzip', 'screen'
			)

def _check_sudo():
	with settings(warn_only=False):
		result = sudo('pwd')
		if result.failed:
			print "Please make sure you have root privileges on the server."

def _get_os():
	global platform
	platform = None
	oscheck = sudo('ls /etc/lsb-release')
	if oscheck.succeeded:
		platform = 'Ubuntu'
	oscheck = sudo('ls /etc/redhat-release')
	if oscheck.succeeded:
		platform = 'RedHat'
	oscheck = sudo('ls /etc/zones')
	if oscheck.succeeded:
		platform = 'Solaris'
	if(not platform):
		raise NameError('Could not determine host OS !')

def mkdir(dir, use_sudo=False):
	if (use_sudo):
		run('if [ ! -d %s ]; then mkdir -p %s; fi;' % (dir, dir))
	else:
		sudo('if [ ! -d %s ]; then mkdir -p %s; fi;' % (dir, dir))

def provision():
	global hostname
	hostname = sudo('hostname | awk -F \'.\' \'{print $1}\'')
	global ip 
	ip = sudo('/sbin/ifconfig -a | grep \'inet 192\' | awk \'{print $2}\'')

def prepare():
	sudo('rm -fr ~/nrpe_install* ~/nagios-plugins* ~/nrpe-2* nagios-nrpe.xml* nrpe_install.sh* /tmp/%s.cfg /tmp/nagios-plugins* /tmp/nrpe*' % hostname)
#	 with settings(
#       hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
	sudo('groupadd nagios')
	sudo('useradd -c \'nagios system user\' -d /usr/local/nagios -s /bin/bash -g nagios -m nagios')
	sudo('chown -R nagios:nagios /usr/local/nagios/')
	if platform == 'Solaris':
		sudoers_check = sudo('cat /opt/local/etc/sudoers | grep -i nagios | wc -l')
		if sudoers_check == '0':
			sudo('echo "nagios ALL=(ALL) NOPASSWD: ALL" >> /opt/local/etc/sudoers')
		sudo('pkgin -y in %s' % ' '.join(PACKAGES_SOLARIS))
	if platform ==  'Ubuntu':
		sudoers_check = sudo('cat /etc/sudoers | grep -i nagios | wc -l')
		if sudoers_check == '0':
			sudo('echo "nagios ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers')
		sudo('apt-get -y install %s' % ' '.join(PACKAGES_UBUNTU))

def sources():
	with cd('/tmp'):
		sudo('wget %s' % NRPE_LINK)
		sudo('tar xzf nrpe-%s.tar.gz' % NRPE_VERSION)
		sudo ('wget %s' % NAGIOS_PLUGINS_LINK)
		sudo ('tar xzf nagios-plugins-%s.tar.gz' % NAGIOS_PLUGINS_VERSION)

def install_nrpe():
	with cd('/tmp/nrpe-%s' % NRPE_VERSION):
		if platform == 'Solaris':
			with settings(warn_only=False):
				sudo('gsed -i \'s/log_facility=LOG_AUTHPRIV;/log_facility=LOG_AUTH;/\' src/nrpe.c')
				sudo('gsed -i \'s/log_facility=LOG_FTP;/log_facility=LOG_DAEMON;/\' src/nrpe.c')
			sudo('./configure --with-ssl-lib=/usr/sfw/lib --with-ssl-inc=/usr/sfw/include --with-ssl=/usr/sfw --enable-command-args')
			sudo('gmake all')
			sudo('gmake install-plugin')
			sudo('gmake install-daemon')
			sudo('gmake install-daemon-config')
		if platform == 'Ubuntu':
			sudo('postgresql-client-9.1')
		sudo('printf "nrpe\t\t5666/tcp\t\t\t#NRPE" >> /etc/services')
	with cd('/tmp'):
		sudo('pkill nrpe')
		with settings(warn_only=False):
			if platform == 'Solaris':
				# with put('%s/nagios-nrpe.xml' % SKELETON_DIR, '/tmp/', use_sudo=True, mirror_local_mode=False, mode=755):
				# 	sudo('svccfg import nagios-nrpe.xml')
				put('%s/nagios-nrpe.xml' % SKELETON_DIR, '/tmp', mode=755)
				sudo('svccfg import nagios-nrpe.xml')
#				sudo('svcadm enable nrpe')


def install_nagios_plugins():
	with cd('/tmp/nagios-plugins-%s' % NAGIOS_PLUGINS_VERSION):
		if platform == 'Solaris':
			sudo('./configure --enable-extra-opts --without-mysql --without-pgsql')
			sudo('gmake')
			sudo('gmake install')


def prepare_plugins():
	mkdir('/usr/local/nagios/libexec/eventhandlers')
	sudo('chmod -R 750 /usr/local/nagios/libexec/eventhandlers')
	mkdir('/usr/local/nagios/var')
	sudo('chmod -R 750 /usr/local/nagios/var')

def clean_plugins(env):
	sudo('rm -f /usr/local/nagios/libexec/check_memory_solaris')
	sudo('rm -f /usr/local/nagios/libexec/check_unicorn')
	sudo('rm -f /usr/local/nagios/libexec/check_unicorn_processes')
	sudo('rm -f /usr/local/nagios/libexec/check_unicorn_memory')
	sudo('rm -f /usr/local/nagios/libexec/eventhandlers/restart-unicorn')
	sudo('rm -f /usr/local/nagios/libexec/eventhandlers/kill-unicorn')
	sudo('rm -f /usr/local/nagios/libexec/check_dj')
	sudo('rm -f /usr/local/nagios/libexec/check_dj_workers')
	sudo('rm -f /usr/local/nagios/libexec/check_dj_workers_yaml')
	sudo('rm -f /usr/local/nagios/libexec/eventhandlers/restart-dj-worker-yaml')
	sudo('rm -f /usr/local/nagios/libexec/eventhandlers/restart-dj-workers-yaml')
	sudo('rm -f /usr/local/nagios/libexec/pmp-check-*')
	sudo('rm -f /usr/local/nagios/libexec/eventhandlers/pmp-check*')
	sudo('rm -f ~/pmp-check-*')
	sudo('rm -f /usr/local/nagios/libexec/check_service')
	sudo('rm -f /usr/local/nagios/libexec/check_redis')
	sudo('rm -f /usr/local/nagios/libexec/check_dj')
	sudo('rm -f /usr/local/nagios/libexec/check_dj_workers')
#	sudo('%s/nrpe.cfg' % env.nrpe_cfg_location)

def upload_plugins(env):
	put('../check_memory_solaris/check_memory_solaris', '/usr/local/nagios/libexec', mode=0755)
	put('../check_unicorn/check_unicorn', '/usr/local/nagios/libexec', mode=0755)
	put('../check_unicorn/check_unicorn_processes', '/usr/local/nagios/libexec', mode=0755)
	put('../check_unicorn_memory/check_unicorn_memory', '/usr/local/nagios/libexec', mode=0755)
	put('../check_unicorn_memory/restart-unicorn', '/usr/local/nagios/libexec/eventhandlers', mode=0750)
	put('../check_unicorn_memory/kill-unicorn', '/usr/local/nagios/libexec/eventhandlers', mode=0750)
	put('../check_dj/check_dj', '/usr/local/nagios/libexec', mode=0755)
	put('../check_dj/check_dj_workers', '/usr/local/nagios/libexec', mode=0755)
	put('../check_dj/check_dj_workers_yaml', '/usr/local/nagios/libexec', mode=0755)
	put('../check_dj/restart-dj-workers-yaml', '/usr/local/nagios/libexec/eventhandlers', mode=0750)
	put('../percona-monitoring-plugins-1.0.0/nagios/bin/*', '/usr/local/nagios/libexec', mode=0755)
	put('../check_service/check_service', '/usr/local/nagios/libexec', mode=0755)
	put('../check_redis/check_redis', '/usr/local/nagios/libexec', mode=0755)
	put('%s/nrpe.cfg' % SKELETON_DIR_TMP, env.nrpe_cfg_location, mode=0744)

def apply_perms(env):
	sudo('chown -R %s:%s /usr/local/nagios' % (env.nrpe_user, env.nrpe_group))

def clean():
	sudo('rm -fr ~/nrpe_install* ~/nagios-plugins* ~/nrpe-2* nagios-nrpe.xml* nrpe_install.sh* /tmp/%s.cfg /tmp/nagios-plugins* /tmp/nrpe*' % hostname)

def restart_nrpe():
	if platform == 'Solaris':
		sudo('svcadm disable nrpe')
		with settings(warn_only=False):
			sudo('svcadm enable nrpe')

def deploy_nrpe(nagios_mysql_pass):
	_get_os()
	env.nrpe_allowed_hosts = '192.168.24.58'
	if platform == 'Solaris':
		env.nrpe_command_prefix = '/opt/local/bin/sudo'
	env.nrpe_cfg_location = '/usr/local/nagios/etc/'
	env.nrpe_user = 'nagios'
	env.nrpe_group = 'nagios'
	env.nrpe_server_port = '5666'
	env.nagios_mysql_pass = nagios_mysql_pass

	file_var_replacements = {
		'ENV_NRPE_SERVER_PORT': env.nrpe_server_port,
		'ENV_NRPE_ALLOWED_HOSTS': env.nrpe_allowed_hosts,
		'ENV_NRPE_USER': env.nrpe_user,
		'ENV_NRPE_GROUP': env.nrpe_group,
		'ENV_NRPE_COMMAND_PREFIX': env.nrpe_command_prefix,
		'ENV_NAGIOS_MYSQL_PASS': env.nagios_mysql_pass
    }

	_check_sudo()
	provision()
	prepare()
	sources()
	install_nrpe()
	install_nagios_plugins()
	clean_plugins(env)
	copy_skeleton_to_path(SKELETON_DIR, SKELETON_DIR_TMP, 'nrpe.cfg', file_var_replacements)
	upload_plugins(env)
	apply_perms(env)
	restart_nrpe()