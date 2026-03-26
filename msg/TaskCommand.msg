uint32 task_id

# action (运动指令)：GOTO（去哪）、STOP（停下）。它完全是给底盘和导航栈看的。
string action_type
float32 target_x
float32 target_y

# mode (战术姿态)：比如 0=待机, 1=巡逻, 2=攻击。它是给云台、发射器、UI灯效看的。
uint8 mode
string reason
float32 timeout
