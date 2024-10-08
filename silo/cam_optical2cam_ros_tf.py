from math import pi

import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from scipy.spatial.transform import Rotation as R
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster


class StaticFramePublisher(Node):
  def __init__(self):
    super().__init__("static_base2cam_tf_publisher")

    self.tf_static_broadcaster = StaticTransformBroadcaster(self)

    # Publish static transforms once at startup
    self.make_transforms()

    self.get_logger().info(
      "Silo side: Static camera_optical2cam_ros transform published"
    )

  def make_transforms(self):
    t = TransformStamped()

    t.header.stamp = self.get_clock().now().to_msg()
    t.header.frame_id = "picam_link_optical"
    t.child_frame_id = "picam_link"

    t.transform.translation.x = 0.0
    t.transform.translation.y = 0.0
    t.transform.translation.z = 0.0

    quat = R.from_euler("ZYX", [0.0, -pi / 2, pi / 2]).as_quat()

    t.transform.rotation.x = quat[0]
    t.transform.rotation.y = quat[1]
    t.transform.rotation.z = quat[2]
    t.transform.rotation.w = quat[3]

    self.tf_static_broadcaster.sendTransform(t)


def main():
  rclpy.init()
  node = StaticFramePublisher()
  try:
    rclpy.spin(node)
  except KeyboardInterrupt:
    pass

  rclpy.shutdown()
