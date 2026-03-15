#!/usr/bin/env python
# -*- coding: utf-8 -*-
import math
import rospy
from geometry_msgs.msg import PoseStamped
from robot_vs.msg import RobotCommand


class RobotPatrolState(object):
    """每台机器人在巡逻策略中的内部状态。"""

    def __init__(self, target_idx):
        self.target_idx = target_idx
        self.arrived_latched = False
        self.arrived_time = None
        self.last_sent_idx = None
        self.last_publish_time = rospy.Time(0)


class PatrolPolicy(object):
    """测试巡逻策略，后续可替换成更复杂协同策略。"""

    def __init__(self, robot_ns_list):
        raw_points = rospy.get_param("~patrol/points", [[0.5, 0.0], [0.5, 1.0], [0.0, 1.0]])
        self.patrol_points = self._parse_points(raw_points)
        self.arrive_radius = rospy.get_param("~patrol/arrive_radius", 0.12)
        self.leave_radius = rospy.get_param("~patrol/leave_radius", 0.20)
        self.arrive_hold_s = rospy.get_param("~patrol/arrive_hold_s", 1.0)
        self.goal_republish_s = rospy.get_param("~patrol/goal_republish_s", 2.0)

        if self.leave_radius < self.arrive_radius:
            self.leave_radius = self.arrive_radius + 0.05

        self.state_dict = {}
        point_count = len(self.patrol_points)
        for i, ns in enumerate(robot_ns_list):
            self.state_dict[ns] = RobotPatrolState(i % point_count)

    def _parse_points(self, raw_points):
        points = []
        for point in raw_points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            points.append((float(point[0]), float(point[1])))

        if not points:
            rospy.logwarn("patrol/points is invalid, fallback to default points")
            points = [(0.5, 0.0), (0.5, 1.0), (0.0, 1.0)]

        return points

    def decide(self, ns, pose):
        """返回当前机器人(nav_goal, robot_cmd)。nav_goal可能为None(无须重发)。"""
        if pose is None:
            return None, None

        state = self.state_dict[ns]
        now = rospy.Time.now()

        target_x, target_y = self.patrol_points[state.target_idx]
        dist = math.hypot(pose.position.x - target_x, pose.position.y - target_y)

        # 到点判定加入锁存与驻留，避免阈值抖动导致频繁切目标
        if not state.arrived_latched and dist <= self.arrive_radius:
            state.arrived_latched = True
            state.arrived_time = now
            rospy.loginfo("[%s] reached waypoint %d, hold %.1fs", ns, state.target_idx, self.arrive_hold_s)
        elif state.arrived_latched:
            if dist >= self.leave_radius:
                state.arrived_latched = False
                state.arrived_time = None
            elif (now - state.arrived_time).to_sec() >= self.arrive_hold_s:
                state.target_idx = (state.target_idx + 1) % len(self.patrol_points)
                state.arrived_latched = False
                state.arrived_time = None
                target_x, target_y = self.patrol_points[state.target_idx]
                rospy.loginfo("[%s] switch to waypoint %d (%.2f, %.2f)", ns, state.target_idx, target_x, target_y)

        robot_cmd = RobotCommand()
        robot_cmd.mode = 1
        robot_cmd.attack = False
        robot_cmd.goal_x = target_x
        robot_cmd.goal_y = target_y

        should_publish_goal = False
        if state.last_sent_idx != state.target_idx:
            should_publish_goal = True
        elif (now - state.last_publish_time).to_sec() >= self.goal_republish_s:
            should_publish_goal = True

        nav_goal = None
        if should_publish_goal:
            nav_goal = PoseStamped()
            nav_goal.header.frame_id = "map"
            nav_goal.header.stamp = now
            nav_goal.pose.position.x = target_x
            nav_goal.pose.position.y = target_y
            nav_goal.pose.orientation.w = 1.0
            state.last_sent_idx = state.target_idx
            state.last_publish_time = now

        return nav_goal, robot_cmd


class DecisionEngine:
    def __init__(self, robot_ns_list):
        self.robot_ns_list = list(robot_ns_list)
        self.patrol_policy = PatrolPolicy(self.robot_ns_list)

    def make_team_decision(self, team_state):
        """团队决策：输入全体感知，输出每台机器人(nav_goal, robot_cmd)。"""
        actions = {}
        for ns in self.robot_ns_list:
            state = team_state.get(ns, {})
            pose = state.get("pose")
            image = state.get("image")
            nav_goal, robot_cmd = self._make_single_robot_decision(ns, pose, image)
            actions[ns] = (nav_goal, robot_cmd)

        return actions

    def _make_single_robot_decision(self, ns, pose, image):
        """单车决策子过程：当前先保留巡逻逻辑，后续可替换为协同策略。"""
        _ = image
        return self.patrol_policy.decide(ns, pose)