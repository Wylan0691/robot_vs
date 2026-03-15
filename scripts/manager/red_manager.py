#!/usr/bin/env python
# -*- coding: utf-8 -*-
import rospy
from geometry_msgs.msg import Twist
from perception import Perception
from decision import DecisionEngine
from executor import Executor

class RedTeamManager:
    def __init__(self):
        # 初始化节点，指定命名空间
        rospy.init_node("red_team_manager")
        # 红方两台机器人的命名空间列表
        self.robot_ns_list = ["robot_red", "robot_red2"]  
        
        # 为每台机器人初始化 感知/执行 模块
        self.perception_dict = {}
        self.executor_dict = {}
        for ns in self.robot_ns_list:
            self.perception_dict[ns] = Perception(ns)
            self.executor_dict[ns] = Executor(ns)

        # 团队级决策器：统一接收全队感知结果后再输出分车指令
        self.decision_engine = DecisionEngine(self.robot_ns_list)

        self.rate = rospy.Rate(10)  # 决策频率
        rospy.loginfo("红方TeamManager启动完成")

    # 在你的red_manager.py里，初始化完成后，添加这段代码
    def trigger_amcl_convergence(self, ns):
        """自动发布微小运动,触发AMCL收敛"""
        pub = rospy.Publisher(f"/{ns}/cmd_vel", Twist, queue_size=10)
        rospy.sleep(1)
        
        # 发布一个向前10cm的运动
        vel = Twist()
        vel.linear.x = 0.2
        pub.publish(vel)
        rospy.sleep(0.5)
        
        # 发布一个向后10cm的运动，回到原位
        vel.linear.x = -0.2
        pub.publish(vel)
        rospy.sleep(0.5)
        
        # 停止
        vel.linear.x = 0.0
        pub.publish(vel)
        rospy.loginfo(f"{ns} AMCL收敛触发完成")

    def run(self):
        """主循环：感知汇总 -> 团队决策 -> 分车执行"""
        while not rospy.is_shutdown():
            team_perception = {}
            for ns in self.robot_ns_list:
                # 1. 感知：获取当前机器人的位置/图像数据
                pose = self.perception_dict[ns].get_current_pose()
                image = self.perception_dict[ns].get_current_image()
                team_perception[ns] = {
                    "pose": pose,
                    "image": image,
                }

            # 2. 决策：统一使用全队状态做协同决策
            team_actions = self.decision_engine.make_team_decision(team_perception)

            # 3. 执行：按机器人分发指令
            for ns in self.robot_ns_list:
                nav_goal, robot_cmd = team_actions.get(ns, (None, None))
                if nav_goal:
                    self.executor_dict[ns].publish_nav_goal(nav_goal)
                if robot_cmd:
                    self.executor_dict[ns].publish_robot_command(robot_cmd)

            self.rate.sleep()

if __name__ == '__main__':
    try:
        manager = RedTeamManager()
        manager.run()
    except rospy.ROSInterruptException:
        pass