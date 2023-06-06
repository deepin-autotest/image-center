from image_center.server import server
from image_center.conf import setting

setting.PORT = 8889  # 默认端口是8889，可以修改为其他端口；

server()