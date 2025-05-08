from setuptools import setup, find_packages

setup(
    name='dq_monitor',
    version='0.1.0',
    description='Data Quality Monitoring CLI and orchestration tool for DHIS2',
    author='Your Name',
    packages=find_packages(),
    install_requires=[
        'aiohttp',
        'PyYAML',
        'python-dateutil',
        'flask'
    ],
    entry_points={
        'console_scripts': [
            'dq-monitor=app.runner:run_main'
        ]
    },
    python_requires='>=3.8',
)
