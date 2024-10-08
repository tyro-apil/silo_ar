from typing import List, Tuple

import rclpy
from rclpy.node import Node
from silo_msgs.msg import Silo, SiloArray
from yolov8_msgs.msg import BoundingBox2D, Detection, DetectionArray


class StateEstimation(Node):
  def __init__(self):
    super().__init__("state_estimation")

    self.declare_parameter("team_color", "blue")
    self.declare_parameter("width", 921)
    self.declare_parameter("height", 518)
    self.declare_parameter("min_silo_area", 1500)

    self.silos_state_publisher = self.create_publisher(SiloArray, "state_image", 10)
    self.detections_subscriber = self.create_subscription(
      DetectionArray, "yolo/tracking", self.detections_callback, 10
    )
    self.detections_subscriber

    self.silos_state_msg = SiloArray()
    team_color = self.get_parameter("team_color").get_parameter_value().string_value

    ########################################
    # self.silo_order_descending = False
    if team_color == "blue":
      self.silo_order_descending = False
    else:
      self.silo_order_descending = True

    ########################################

    self.__image_width = self.get_parameter("width").get_parameter_value().integer_value
    self.__image_height = (
      self.get_parameter("height").get_parameter_value().integer_value
    )
    self.__min_silo_area = (
      self.get_parameter("min_silo_area").get_parameter_value().integer_value
    )
    self.__tolerance = 0.05

    self.state = None
    self.silos_num = None
    self.balls_num = None
    self.get_logger().info("Silo state estimation node started.")

  def detections_callback(self, detections_msg: DetectionArray):
    # breakpoint()
    # filter detections
    silos, balls = self.separate_detections(detections_msg.detections)
    silos = self.filter_silos(silos)
    self.silos_num = len(silos)
    self.balls_num = len(balls)

    # self.get_logger().info(
    #   f"Detected {self.silos_num} silos and {self.balls_num} balls"
    # )
    if self.silos_num > 5:
      self.get_logger().warn("Too many silos detected")
      return

    # sort silos
    sorted_silos = sorted(
      silos, key=lambda x: x.bbox.center.position.x, reverse=self.silo_order_descending
    )

    # get region of interest of detected silos
    silo_bboxes_xywh = [self.parse_bbox(silo.bbox) for silo in sorted_silos]
    silo_bboxes_xyxy = [self.xywh2xyxy(silo_bbox) for silo_bbox in silo_bboxes_xywh]

    state = [[] for _ in range(len(silos))]
    # iterate through detected balls and check if they are inside the silos
    for ball in balls:
      ball_bbox_xywh = self.parse_bbox(ball.bbox)
      ball_bbox_xyxy = self.xywh2xyxy(ball_bbox_xywh)
      for i, silo_bbox in enumerate(silo_bboxes_xyxy):
        if (
          ball_bbox_xyxy[0]
          >= max(0, silo_bbox[0] - self.__tolerance * self.__image_width)
          and ball_bbox_xyxy[2]
          <= min(
            self.__image_width, silo_bbox[2] + self.__tolerance * self.__image_width
          )
          and ball_bbox_xyxy[1] >= max(0, silo_bbox[1] - 100)
          and ball_bbox_xyxy[3] <= min(self.__image_height, silo_bbox[3] + 10)
        ):
          state[i].append(ball)
          break

    # sort balls inside silo by y_coordinate
    for i in range(len(state)):
      state[i].sort(key=lambda ball: ball.bbox.center.position.y, reverse=True)
      if len(state[i]) > 3:
        self.get_logger().warn(
          f"Too many balls detected in silo-{i+1} i.e. {len(state[i])} balls"
        )
        state[i] = state[i][:3]

    # stringify the state of silos
    state_repr = self.stringify_state(state)
    silos_state_msg = self.get_silo_state_msg(state_repr, silo_bboxes_xyxy)

    # update state with strings for each silo
    self.update_state(state_repr)
    # self.display_state()

    # publish the state of silos
    self.silos_state_msg = silos_state_msg
    self.silos_state_publisher.publish(silos_state_msg)

  def separate_detections(
    self, detections: List[Detection]
  ) -> Tuple[List[Detection], List[Detection]]:
    silos = list(filter(lambda detection: detection.class_name == "silo", detections))
    balls = list(
      filter(
        lambda detection: detection.class_name != "silo"
        and (detection.class_name != "purple" or detection.class_name != "purple-ball"),
        detections,
      )
    )
    return silos, balls

  def filter_silos(self, silos: List[Detection]) -> List[Detection]:
    return silos
    filtered_silos = []
    for silo in silos:
      xywh = self.parse_bbox(silo.bbox)
      area = xywh[2] * xywh[3]
      if area > self.__min_silo_area:
        filtered_silos.append(silo)
    return filtered_silos

  def parse_bbox(self, bbox_xywh: BoundingBox2D) -> List[int]:
    """! Parse bbox from BoundingBox2D msg
    @param bbox_xywh a BoundingBox2D msg in format xywh
    @return a tuple of center_x, center_y, width, height
    """
    center_x = int(bbox_xywh.center.position.x)
    center_y = int(bbox_xywh.center.position.y)
    width = int(bbox_xywh.size.x)
    height = int(bbox_xywh.size.y)
    return [center_x, center_y, width, height]

  def xywh2xyxy(self, xywh: List[int]) -> List[int]:
    """Converts bbox xywh format into xyxy format"""
    xyxy = []
    xyxy.append(xywh[0] - int(xywh[2] / 2))
    xyxy.append(xywh[1] - int(xywh[3] / 2))
    xyxy.append(xywh[0] + int(xywh[2] / 2))
    xyxy.append(xywh[1] + int(xywh[3] / 2))
    return xyxy

  def stringify_state(self, state: List[List[Detection]]) -> List[str]:
    state_repr = [None] * self.silos_num
    for i, silo in enumerate(state):
      silo_state = ""
      for ball in silo:
        if ball.class_name == "red" or ball.class_name == "red-ball":
          silo_state += "R"
        elif ball.class_name == "blue" or ball.class_name == "blue-ball":
          silo_state += "B"
      state_repr[i] = silo_state
    return state_repr

  def update_state(self, state_repr: List[str]) -> None:
    self.state = state_repr

  def display_state(self) -> None:
    log = ""
    for i, silo in enumerate(self.state):
      log += f"Silo{i+1}: {silo} | "
    self.get_logger().info(log)

  def get_silo_state_msg(
    self, silos_state: List[str], silo_bboxes_xyxy: List[List[int]]
  ) -> SiloArray:
    silo_state_msg = SiloArray()
    for i, state in enumerate(silos_state):
      silo_msg = Silo()
      silo_msg.index = i + 1
      silo_msg.state = state
      silo_msg.xyxy[0] = silo_bboxes_xyxy[i][0]
      silo_msg.xyxy[1] = silo_bboxes_xyxy[i][1]
      silo_msg.xyxy[2] = silo_bboxes_xyxy[i][2]
      silo_msg.xyxy[3] = silo_bboxes_xyxy[i][3]
      silo_state_msg.silos.append(silo_msg)
    return silo_state_msg


def main(args=None):
  rclpy.init(args=args)

  state_estimation_node = StateEstimation()

  rclpy.spin(state_estimation_node)

  # Destroy the node explicitly
  # (optional - otherwise it will be done automatically
  # when the garbage collector destroys the node object)
  state_estimation_node.destroy_node()
  rclpy.shutdown()


if __name__ == "__main__":
  main()
