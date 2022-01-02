"""
.. module:: setup
    :platform: Multiplatform
    :synopsis: runltp-ng setuptools script

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from setuptools import setup, find_packages

setup(
    name="runltp-ng",
    version="1.0",
    author="Andrea Cervesato",
    author_email="andrea.cervesato@suse.com",
    description="Next Generation LTP runner",
    url="https://www.suse.com",
    long_description=open('README.md').read(),
    platforms=["linux"],
    python_requires=">=3.6,<3.11",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: POSIX",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Utilities",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
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
    # requirements to run this script
    setup_requires=[
        "setuptools",
    ],
    # install requirements
    entry_points={
        # marvin command
        'console_scripts': [
            'runltp-ng = ltp.main:run',
        ],
    },
)
