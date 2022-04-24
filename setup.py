"""
.. module:: setup.py
    :platform: Linux
    :synopsis: setuptools configuration script

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from setuptools import setup, find_packages


setup(
    name="runltp-ng",
    version="0.1.0",
    author="Andrea Cervesato",
    author_email="andrea.cervesato@suse.com",
    description="Next generation runltp",
    url="https://www.suse.com",
    long_description=open('README.md').read(),
    platforms=["linux"],
    python_requires=">3.5,<3.11",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: LTP",
        "Intended Audience :: Developers",
        "Operating System :: POSIX",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Utilities",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]
    ),
    # this will include MANIFEST.in if defined
    include_package_data=True,
    # install requirements
    install_requires=[
        "paramiko<=2.10.3",
        "scp<=0.14.4",
        "rich<=12.2.0"
    ],
    # requirements to run this script
    setup_requires=[
        "setuptools",
    ],
    # install requirements
    entry_points={
        # main command
        'console_scripts': [
            'runltp-ng = ltp.main:run',
        ],
    },
)
