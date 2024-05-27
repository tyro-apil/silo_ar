from setuptools import find_packages, setup

package_name = 'silo'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='apil',
    maintainer_email='078bct017.apil@pcampus.edu.np',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'cam_optical2cam_ros_tf = transforms.cam_optical2cam_ros:main',
            'base2cam_optical_tf = transforms.base2cam_optical:main',   
        ],
    },
)
