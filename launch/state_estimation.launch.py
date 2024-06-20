#! /usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
  camera_info_config = os.path.join(
    get_package_share_directory("silo"), "config", "camera_info.yaml"
  )

  base2cam_config = os.path.join(
    get_package_share_directory("silo"), "config", "base2cam.yaml"
  )

  silo_config = os.path.join(get_package_share_directory("silo"), "config", "silo.yaml")

  namespace = LaunchConfiguration("namespace")
  namespace_cmd = DeclareLaunchArgument(
    "namespace", default_value="", description="Name of the namespace"
  )

  pose_topic = LaunchConfiguration("pose_topic")
  pose_topic_cmd = DeclareLaunchArgument(
    "pose_topic",
    default_value="/odometry/filtered",
    description="Name of the pose topic of map2base transform",
  )

  tracking_topic = LaunchConfiguration("tracking_topic")
  tracking_topic_cmd = DeclareLaunchArgument(
    "tracking_topic",
    default_value="yolo/tracking",
    description="Name of the tracking topic",
  )

  team_color = LaunchConfiguration("team_color", default="blue")
  team_color_cmd = DeclareLaunchArgument(
    "team_color",
    default_value="blue",
    description="Team color of the robot (blue or red)",
  )

  state_estimation_node_cmd = Node(
    package="silo",
    namespace=namespace,
    executable="state_estimation_node",
    name="state_estimation_node",
    parameters=[{"team_color": team_color}],
    remappings=[("yolo/tracking", tracking_topic), ("/odometry/filtered", pose_topic)],
  )

  silo_matching_node_cmd = Node(
    package="silo",
    namespace=namespace,
    executable="silo_matching_node",
    name="silo_matching_node",
    parameters=[camera_info_config, base2cam_config, silo_config],
  )

  ld = LaunchDescription()

  ld.add_action(namespace_cmd)
  ld.add_action(pose_topic_cmd)
  ld.add_action(tracking_topic_cmd)
  ld.add_action(team_color_cmd)

  ld.add_action(state_estimation_node_cmd)
  # ld.add_action(silo_matching_node_cmd)

  return ld
