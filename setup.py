#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from setuptools import setup, find_packages
from pip._internal.req import parse_requirements

# Parse requirements from requirements.txt file
install_reqs = parse_requirements('requirements.txt', session='dummy')
requirements = [str(ir.requirement) for ir in install_reqs]

setup(
    name='badminton-video-trimmer',
    version='1.0.0',
    packages=find_packages('.', exclude=['tests']),
    author='Phu Binh Dang',
    author_email='binhdang211@gmail.com',
    description='Tool for automated badminton video trimming',
    long_description=open('README.md').read(),
    zip_safe=False,
)
