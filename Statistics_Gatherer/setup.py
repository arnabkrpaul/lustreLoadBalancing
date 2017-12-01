import setuptools

import glob
import sys

# plugins = glob.glob("metric*.py")

if sys.version_info[:3] < (2,6,0):
    raise RuntimeError("This application requires Python 2.6+")

details="""
More details on the package
"""

setuptools.setup(name='oddmon',
    description="A distributed monitoring tool suite",
    url="http://github.com/ORNL-TechInt/oddmon",
    license="LGPL",
    version='1.4.2',
    author='Feiyi Wang, Ross Miller, Jeremy Anantharaj',
    author_email='fwang2@ornl.gov, rgmiller@ornl.gov, anantharajjd@ornl.gov',
    packages = ['oddmon', 'oddmon.metric_plugins'],
    # Note: metrics isn't technically a package (it has no __init__.py), but
    # it is where all of the plugins live and we definitely want to include
    # them in the distribution...
    # ToDo: explore using setuptools.findpackages()
    scripts = ['monctl.py'],
    data_files=[ ('/etc/oddmon', ['oddmon.cfg.sample']),
                 ('share/doc/oddmon', ['README.md']),
                 ('/etc/init', ['oddmon_aggregator.conf','oddmon_collector.conf'])
               ],
    classifiers=[
            'Development Status :: 3 - Alpha',
            'Intended Audience :: System Administrators',
            'Topic :: System :: Monitoring',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
      ],
    # Work around distutils' lack of "%config(noreplace)" support by using a
    # post install scriptlet to copy /etc/oddmon/oddmon.cfg.sample over to
    # /etc/oddmon/oddmon.cfg *IF* the latter file doesn't already exist.
    # We could also add a "post_uninstall" option if we need it.
    options = { 'bdist_rpm':{'post_install' : 'post_install'}},
    long_description=details
      )


