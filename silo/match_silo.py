import cv2
import numpy as np
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from scipy.spatial.transform import Rotation as R
from silo_msgs.msg import SiloArray


class SiloMatching(Node):
  def __init__(self):
    super().__init__("silo_matching_node")
    self.declare_parameter("team_color", "blue")
    self.declare_parameter("silos_x", [0.0] * 5)
    self.declare_parameter("silo_z_min", 0.0)
    self.declare_parameter("silo_z_max", 0.0)
    self.declare_parameter("silo_y", 0.0)
    self.declare_parameter("silo_radius", 0.0)
    self.declare_parameter("translation", [0.0] * 3)  # camera translation
    self.declare_parameter("ypr", [0.0] * 3)  # camera orientation
    self.declare_parameter("k", [0.0] * 9)  # camera matrix

    self.declare_parameter("image_reliability", QoSReliabilityPolicy.BEST_EFFORT)

    odometry_qos_profile = QoSProfile(depth=10)
    odometry_qos_profile.reliability = QoSReliabilityPolicy.BEST_EFFORT

    self.silos_state_map_publisher = self.create_publisher(SiloArray, "state_map", 10)
    self.baselink_pose_subscriber = self.create_subscription(
      Odometry,
      "/odometry/filtered",
      self.baselink_pose_callback,
      qos_profile=odometry_qos_profile,
    )
    self.baselink_pose_subscriber
    self.silos_state_subscriber = self.create_subscription(
      SiloArray, "state_image", self.silo_state_callback, 10
    )
    self.silos_state_subscriber

    self.translation_map2base = None
    self.quaternion_map2base = None
    self.tf_base2map = None

    self.cam_translation = (
      self.get_parameter("translation").get_parameter_value().double_array_value
    )
    self.cam_ypr = self.get_parameter("ypr").get_parameter_value().double_array_value
    cam_orientation = R.from_euler("ZYX", self.cam_ypr, degrees=True)
    tf_base2cam = np.eye(4)
    tf_base2cam[:3, 3] = self.cam_translation
    tf_base2cam[:3, :3] = cam_orientation.as_matrix()
    self.tf_cam2base = np.linalg.inv(tf_base2cam)

    self.silos_x = (
      self.get_parameter("silos_x").get_parameter_value().double_array_value
    )
    self.silo_z_min = (
      self.get_parameter("silo_z_min").get_parameter_value().double_value
    )
    self.silo_z_max = (
      self.get_parameter("silo_z_max").get_parameter_value().double_value
    )
    self.silo_y = self.get_parameter("silo_y").get_parameter_value().double_value
    self.silo_radius = (
      self.get_parameter("silo_radius").get_parameter_value().double_value
    )

    self.camera_matrix = np.array(
      self.get_parameter("k").get_parameter_value().double_array_value
    ).reshape(3, 3)
    self.silos_roi_map = self.get_silos_map_coordinates()
    self.silos_roi_pixel = None
    # breakpoint()
    self.get_logger().info("Silo matching node started.")

  def silo_state_callback(self, silos_state_msg: SiloArray):
    # breakpoint()
    if self.tf_base2map is None:
      self.get_logger().warn("Base link pose not received yet")
      return

    # Transform coordinates for each silo in pixel-coordinates
    self.silos_roi_pixel = self.get_silos_pixel_coordinates()

    silos_state_map = SiloArray()
    # Assign absolute index to each silo based on IoU with silo regions
    for i, silo in enumerate(silos_state_msg.silos):
      silo_map = silo
      for j, silo_projected in enumerate(self.silos_roi_pixel):
        # breakpoint()
        iou, intersection = self.calculate_iou(silo.xyxy, silo_projected["bbox"])
        if iou != 0.0:
          if iou > 0.5:
            silo_map.index = j
            break
          else:
            self.get_logger().warn(
              f"Silo-{i+1} has low IoU with Silo-{j+1} i.e. {iou:.2f}"
            )

        if j == len(self.silos_roi_pixel) - 1:
          self.get_logger().warn(f"Silo-{i+1} not found in the map")
          silo_map.index = 255
      silos_state_map.silos.append(silo_map)

    self.silos_state_map_publisher.publish(silos_state_map)

  def get_silos_map_coordinates(self):
    silos_roi_map = []
    for i, y in enumerate(self.silos_x):
      silo_info = {}
      top_left = (self.silo_y, y + self.silo_radius, self.silo_z_max)
      bottom_right = (self.silo_y, y - self.silo_radius, self.silo_z_min)
      silo_info["index"] = i + 1
      silo_info["roi"] = (top_left, bottom_right)
      silos_roi_map.append(silo_info)
    return silos_roi_map

  def get_silos_pixel_coordinates(self):
    pixel_coordinates = []
    for i, silo in enumerate(self.silos_roi_map):
      silo_info = {}
      top_left_base = self.map2base(list(silo["roi"][0]))
      bottom_right_base = self.map2base(list(silo["roi"][1]))

      top_left_cam = self.base2cam(top_left_base)
      bottom_right_cam = self.base2cam(bottom_right_base)

      top_left_pixel = self.cam2pixel(top_left_cam)
      bottom_right_pixel = self.cam2pixel(bottom_right_cam)

      silo_info["index"] = i + 1
      silo_info["bbox"] = top_left_pixel + bottom_right_pixel

      pixel_coordinates.append(silo_info)
    return pixel_coordinates

  def calculate_iou(self, bbox1, bbox2):
    # breakpoint()
    x_left = max(bbox1[0], bbox2[0])
    y_top = max(bbox1[1], bbox2[1])
    x_right = min(bbox1[2], bbox2[2])
    y_bottom = min(bbox1[3], bbox2[3])

    if x_right < x_left or y_bottom < y_top:
      return 0.0, None

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    union_area = bbox1_area + bbox2_area - intersection_area

    iou = intersection_area / union_area
    return iou, [x_left, y_top, x_right, y_bottom]

  def baselink_pose_callback(self, pose_msg: Odometry):
    self.translation_map2base = np.zeros(3)
    self.translation_map2base[0] = pose_msg.pose.pose.position.x
    self.translation_map2base[1] = pose_msg.pose.pose.position.y
    self.translation_map2base[2] = pose_msg.pose.pose.position.z

    self.quaternion_map2base = np.zeros(4)
    self.quaternion_map2base[0] = pose_msg.pose.pose.orientation.x
    self.quaternion_map2base[1] = pose_msg.pose.pose.orientation.y
    self.quaternion_map2base[2] = pose_msg.pose.pose.orientation.z
    self.quaternion_map2base[3] = pose_msg.pose.pose.orientation.w

    tf_map2base = np.eye(4)
    tf_map2base[:3, :3] = R.from_quat(self.quaternion_map2base).as_matrix()
    tf_map2base[:3, 3] = self.translation_map2base
    self.tf_base2map = np.linalg.inv(tf_map2base)

  def map2base(self, map_coordinates):
    map_coordinates.append(1.0)
    map_coordinates_homogeneous = np.array(map_coordinates).reshape((-1, 1))
    base_coordinates_homogeneous = self.tf_base2map @ map_coordinates_homogeneous
    base_coordinates = base_coordinates_homogeneous / base_coordinates_homogeneous[-1]
    return base_coordinates[:-1].reshape(-1).tolist()

  def base2cam(self, base_coordinates):
    base_coordinates.append(1.0)
    base_coordinates_homogeneous = np.array(base_coordinates).reshape((-1, 1))
    cam_coordinates_homogeneous = self.tf_cam2base @ base_coordinates_homogeneous
    cam_coordinates = cam_coordinates_homogeneous / cam_coordinates_homogeneous[-1]
    return cam_coordinates[:-1].reshape(-1).tolist()

  def cam2pixel(self, cam_coordinates):
    cam_coordinates = np.array(cam_coordinates).reshape((-1, 1))
    pixel_coordinates_homogeneous = self.camera_matrix @ cam_coordinates
    pixel_coordinates = (
      pixel_coordinates_homogeneous / pixel_coordinates_homogeneous[-1]
    )
    return pixel_coordinates[:-1].reshape(-1).tolist()

  def parse_bbox(self, bbox_xyxy):
    return [bbox_xyxy[0], bbox_xyxy[1], bbox_xyxy[2], bbox_xyxy[3]]

  def draw_silos_map(self, img):
    color = (0, 255, 0)
    for silo in self.silos_roi_pixel:
      top_left = (int(silo["bbox"][0]), int(silo["bbox"][1]))
      bottom_right = (int(silo["bbox"][2]), int(silo["bbox"][3]))
      cv2.rectangle(img, top_left, bottom_right, color, 2)
      cv2.putText(
        img,
        f"{silo['index']}",
        (top_left[0] + 5, top_left[1] + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 0),
        2,
      )
    return img

  def draw_silos_detected(self, img, silos):
    color = (255, 0, 255)
    for silo in silos:
      top_left = (int(silo.xyxy[0]), int(silo.xyxy[1]))
      bottom_right = (int(silo.xyxy[2]), int(silo.xyxy[3]))
      cv2.rectangle(img, top_left, bottom_right, color, 2)
      cv2.putText(
        img,
        f"{silo.index}",
        (top_left[0] + 5, top_left[1] + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 0),
        2,
      )
    return img

  def draw_iou(self, img, bbox, iou):
    alpha = 0.5
    overlay = img.copy()
    cv2.rectangle(
      overlay,
      (int(bbox[0]), int(bbox[1])),
      (int(bbox[2]), int(bbox[3])),
      (0, 0, 255),
      -1,
    )

    # Blend the overlay with the image
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.putText(
      img,
      f"{iou:.2f}",
      (bbox[0] + 5, bbox[1] + 20),
      cv2.FONT_HERSHEY_SIMPLEX,
      0.5,
      (0, 255, 0),
      2,
    )
    return img


def main(args=None):
  rclpy.init(args=args)

  state_estimation_node = SiloMatching()

  rclpy.spin(state_estimation_node)

  # Destroy the node explicitly
  # (optional - otherwise it will be done automatically
  # when the garbage collector destroys the node object)
  state_estimation_node.destroy_node()
  rclpy.shutdown()


if __name__ == "__main__":
  main()
