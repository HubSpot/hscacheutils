from setuptools import setup, find_packages

setup(name='hscacheutils',
  version='0.1.1',
  description="Some of Hubspot's python cache utils, namely generational caching",
  long_description=open('README.md').read(),
  author='HubSpot Developer',
  author_email='devteam+hscacheutils@hubspot.com',
  url='http://dev.hubspot.com/',
  license='MIT',
  packages=find_packages(),
  install_requires=[
    "python-memcached==1.47",
    "Django==1.3",
    "django-cache-utils==0.7",
  ],
  platforms=["any"],
)
