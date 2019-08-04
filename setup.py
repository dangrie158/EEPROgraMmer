from setuptools import setup
from os import path
import re

def read(fname):
    return open(path.join(path.dirname(__file__), fname)).read()

setup(
    name='eepro',
    version='0.2.0',
    author='Daniel Grießhaber',
    author_email='dangrie158@gmail.com',
    url='https://github.com/dangrie158/EEPROgraMmer',
    packages=['eepro'],
    include_package_data=True,
    license='MIT',
    description='Arduino based EEPROM Programmer for parallel EEPROMS',
    long_description=read('README.rst'),
    classifiers=[
        'Development Status :: 1 - Planning',
        'Topic :: Utilities',
        'License :: OSI Approved :: MIT License',
    ],
    install_requires=[
        'pyserial',
	'tqdm'
    ],
    entry_points = {
        'console_scripts': ['eepro=eepro.eepro:main'],
    }
)
