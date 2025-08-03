from setuptools import setup, find_packages

setup(
    name='dq_workbench',
    version='0.1.0',
    description='Data Quality Monitoring CLI and orchestration tool for DHIS2',
    author='Global Implementation Team, HISP Center, University of Oslo',
    packages=find_packages(),
    install_requires=[
        'aiohttp',
        'PyYAML',
        'python-dateutil',
        'flask',
        'flask-wtf',
        'numpy',
        'requests',
        'scipy'
    ],
    entry_points={
        'console_scripts': [
            'dq-monitor=app.runner:run_main'
        ],
        'web_ui': [
            'dq-monitor-web=app.web.app'
        ]
    },
    python_requires='>=3.8',
)
