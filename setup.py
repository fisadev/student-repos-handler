#!/usr/bin/env python

from setuptools import setup

setup(
    name='students-repos-handler',
    version='1.0.0',
    description='Simple tool to handle multiple repos at once, oriented to the grading of assignments in UCSE DAR',
    long_description=open('README.rst').read(),
    author='Juan Pedro Fisanotti',
    author_email='fisadev@gmail.com',
    url='https://github.com/fisadev/student-repos-handler',
    license='LICENSE.txt',
    python_requires='>=3.4',
    requires=["termcolor"],
    py_modules=["repos"],
    entry_points={
        "console_scripts": ['repos=repos:main'],
    },
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
)
