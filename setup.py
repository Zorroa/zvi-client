#!/usr/bin/env python3
from setuptools import setup
from datetime import datetime

# See https://packaging.python.org/tutorials/packaging-projects/
# for details about packaging python projects

# Generating distribution archives (run from same directory as this file)
# python3 -m pip install --user --upgrade setuptools wheel
# python3 setup.py sdist bdist_wheel

requirements = [
    "requests",
    "pyOpenSSL",
    "PyJWT",
    "backoff",
    "pytest"
]

setup(
    name='zvi-client',
    version="1.0.1",
    description='Zorroa Visual Intelligence Python Client',
    url='https://github.com/Zorroa/zvi-client',
    license='Apache2',
    package_dir={'': 'pylib'},
    packages=['zmlp', 'zmlp.app', 'zmlp.entity'],
    scripts=[],
    author="Matthew Chambers",
    author_email="support@zorroa.com",
    keywords="machine learning artificial intelligence",
    python_requires='>=3',

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache 2 License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7"
    ],

    include_package_data=True,
    install_requires=requirements
)
