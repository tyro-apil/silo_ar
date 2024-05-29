import rclpy
from rclpy.node import Node

from yolov8_msgs.msg import DetectionArray, BoundingBox2D

def xywh2xyxy(xywh):
  """Converts bbox xywh format into xyxy format"""
  xyxy = []
  xyxy.append(xywh[0]-int(xywh[2]/2))
  xyxy.append(xywh[1]-int(xywh[3]/2))
  xyxy.append(xywh[0]+int(xywh[2]/2))
  xyxy.append(xywh[1]+int(xywh[3]/2))
  return xyxy


class StateEstimation(Node):
  def __init__(self):
    super().__init__('state_estimation')

    self.detections_subscriber = self.create_subscription(
      DetectionArray,
      "tracking",
      self.detections_callback,
      10
    )
    self.detections_subscriber

    self.state = None
    self.silos_num = None
    self.balls_num = None
    self.get_logger().info(f"Silo state estimation node started.")

  def detections_callback(self, detections_msg: DetectionArray):
    # filter detections
    silos, balls = self.filter_detections(detections_msg.detections)
    self.silos_num = len(silos)
    self.balls_num = len(balls)
    if self.silos_num > 5:
      self.get_logger().warn("Too many silos detected")

    # sort silos from left to right
    sorted_silos = sorted(silos, key=lambda x: x.bbox.center.position.x)

    # get region of interest of detected silos 
    silo_bboxes_xywh = [self.parse_bbox(silo.bbox) for silo in sorted_silos]
    silo_bboxes_xyxy = [xywh2xyxy(silo_bbox) for silo_bbox in silo_bboxes_xywh]

    state = [[] for _ in range(len(silos))]
    # iterate through detected balls and check if they are inside the silos
    for ball in balls:
      ball_bbox_xywh = self.parse_bbox(ball.bbox)
      ball_bbox_xyxy = xywh2xyxy(ball_bbox_xywh)
      for i, silo_bbox in enumerate(silo_bboxes_xyxy):
        if ball_bbox_xyxy[0] >= silo_bbox[0] and ball_bbox_xyxy[2] <= silo_bbox[2]:
          state[i].append(ball)
          break
    
    # sort balls inside silo by y_coordinate
    for i in range(len(state)):
      if len(state[i]) > 3:
        self.get_logger().warn(f"Too many balls detected in silo-{i+1} i.e. {len(state[i])} balls")
      state[i].sort(key=lambda ball: ball.bbox.center.position.y)

    # stringify the state of silos
    state_repr = self.stringify_state(state)

    # update state with strings for each silo
    self.update_state(state_repr)
    self.display_state()
  
  def filter_detections(self, detections):
    silos = list(
      filter(lambda detection: detection.class_name == "silo", detections)
    )
    balls = list(
      filter(lambda detection: detection.class_name != "silo" and detection.class_name != "purple-ball", detections)
    )
    return silos, balls

  def parse_bbox(self, bbox_xywh: BoundingBox2D):
    """! Parse bbox from BoundingBox2D msg
    @param bbox_xywh a BoundingBox2D msg in format xywh
    @return a tuple of center_x, center_y, width, height
    """
    center_x = int(bbox_xywh.center.position.x)
    center_y = int(bbox_xywh.center.position.y)
    width = int(bbox_xywh.size.x)
    height = int(bbox_xywh.size.y)
    return [center_x, center_y, width, height]  

  def stringify_state(self, state):
    state_repr = [None]*self.silos_num
    for i, silo in enumerate(state):
      silo_state = ""
      for ball in silo:
        if ball.class_name == "red-ball":
          silo_state += "R"
        elif ball.class_name == "blue-ball":
          silo_state += "B"
      state_repr[i] = silo_state
    return state_repr
  
  def update_state(self, state_repr):
    self.state = state_repr

  def display_state(self):
    log = ""
    for i, silo in enumerate(self.state):
      log += f"Silo{i+1}: {silo} | "
    self.get_logger().info(log)


def main(args=None):
  rclpy.init(args=args)

  state_estimation_node = StateEstimation()

  rclpy.spin(state_estimation_node)

  # Destroy the node explicitly
  # (optional - otherwise it will be done automatically
  # when the garbage collector destroys the node object)
  state_estimation_node.destroy_node()
  rclpy.shutdown()


if __name__ == '__main__':
  main()