import os
import random
import time
import logging
from time import sleep
from xmlrpc.client import Binary
from xmlrpc.client import ServerProxy

try:
    import cv2 as cv
    import numpy as np

    GET_OPENCV_FORM_RPC = False
except ModuleNotFoundError:
    GET_OPENCV_FORM_RPC = True

try:
    import pyscreenshot
    from PIL import Image
except ModuleNotFoundError:
    pass

from image_center.conf import setting

logger = logging.getLogger("image_center")


class TemplateElementNotFound(BaseException):
    """通过模板资源未匹配到对应元素"""

    def __init__(self, *name):
        """
        通过模板资源未匹配到对应元素
        :param name: 命令
        """
        err = f"通过图片资源, 未在屏幕上匹配到元素"
        template = [f"{i}.png" for i in name]
        BaseException.__init__(self, err, *template)


class TemplatePictureNotExist(BaseException):
    """图片资源，文件不存在"""

    def __init__(self, name):
        """
        文件不存在
        :param name: 命令
        """
        err = f"图片资源：{name} 文件不存在!"
        logger.error(err)
        BaseException.__init__(self, err)


class ImageCenter:
    """图像识别的工具类"""

    @staticmethod
    def _match_image_by_opencv(image_path, rate=None, multiple=False):
        """
         图像识别，匹配小图在屏幕中的坐标 x, y
        :param image_path: 图像识别目标文件的存放路径
        :param rate: 匹配度
        :param multiple: 是否返回匹配到的多个目标
        :return: 根据匹配度返回坐标
        """
        if rate is None:
            rate = float(setting.IMAGE_RATE)
        if setting.IS_X11:
            pyscreenshot.grab().save(setting.SCREEN_CACHE)
        else:
            setting.SCREEN_CACHE = (
                os.popen("qdbus org.kde.KWin /Screenshot screenshotFullscreen")
                    .read()
                    .strip("\n")
            )
        template_path = f"{image_path}.png"
        if GET_OPENCV_FORM_RPC:
            server = ServerProxy(setting.OPENCV_SERVER_HOST, allow_none=True)
            source_rb = open(setting.SCREEN_CACHE, "rb")
            template_rb = open(template_path, "rb")
            try:
                source_path = server.image_put(Binary(source_rb.read()))
                source_rb.close()
                tpl_path = server.image_put(Binary(template_rb.read()))
                template_rb.close()
                return server.match_image_by_opencv(tpl_path, source_path, rate, multiple)
            except OSError:
                raise EnvironmentError(f"RPC服务器链接失败. {setting.OPENCV_SERVER_HOST}")
        else:
            if not os.path.exists(template_path):
                raise TemplatePictureNotExist(template_path)
            source = cv.imread(setting.SCREEN_CACHE)
            template = cv.imread(template_path)
            result = cv.matchTemplate(source, template, cv.TM_CCOEFF_NORMED)
            if not multiple:
                pos_start = cv.minMaxLoc(result)[3]
                _x = int(pos_start[0]) + int(template.shape[1] / 2)
                _y = int(pos_start[1]) + int(template.shape[0] / 2)
                similarity = cv.minMaxLoc(result)[1]
                tmp_log = (
                    f"***{template_path[-40:]}"
                    if len(template_path) >= 40
                    else template_path
                )
                if similarity < rate:
                    logger.info(f"{tmp_log} | 相似度:{round(similarity * 100, 2)}% ")
                    return False
                logger.info(f"{tmp_log} | 坐标:{_x, _y} | 相似度:{round(similarity * 100, 2)}%")
                return _x, _y
            else:
                loc = np.where(result >= rate)
                tmp_list_out = []
                tmp_list_in = []
                loc_list = list(zip(*loc))
                for i in range(0, len(loc_list) - 1):
                    tmp_list_in.append(loc_list[i])
                    if (
                            loc_list[i + 1][0] != loc_list[i][0]
                            or (loc_list[i + 1][1] - loc_list[i][1]) > 1
                    ):
                        tmp_list_out.append(tmp_list_in)
                        tmp_list_in = []
                        continue
                    if i == len(loc_list) - 2:
                        tmp_list_in.append(loc_list[-1])
                        tmp_list_out.append(tmp_list_in)
                result_list = []
                x_list, y_list = [], []
                if tmp_list_out:
                    for i in tmp_list_out:
                        for j in i:
                            x_list.append(j[1])
                            y_list.append(j[0])
                        x = np.mean(x_list) + int(template.shape[1] / 2)
                        y = np.mean(y_list) + int(template.shape[0] / 2)
                        result_list.append((x, y))
                        x_list, y_list = [], []
                    result_list.sort(key=lambda x: x[0])
                    return result_list
                return False

    @staticmethod
    def save_temporary_picture(x: int, y: int, width: int, height: int):
        """
         截取屏幕上指定区域图片，保存临时图片，并返回图片路径
        :param x: 左上角横坐标
        :param y: 左上角纵坐标
        :param width: 宽度
        :param height: 高度
        :return: 图片路径
        """
        if setting.IS_X11:
            if not os.path.exists(setting.TMPDIR):
                os.popen(f"mkdir {setting.TMPDIR}")
            _pic_path = f"{setting.TMPDIR}/{int(time.time())}"
            pyscreenshot.grab().save(setting.SCREEN_CACHE)
            pyscreenshot.grab(bbox=(x, y, x + width, y + height)).save(_pic_path + ".png")
            logger.info(f"截取区域左上角 ({x}, {y}), 长宽 {width}, {height}")
            return _pic_path

    @classmethod
    def find_image(cls, *widget, rate: [float, int] = None, multiple: bool = False, match_number: int = None):
        """
         在屏幕中区寻找小图，返回坐标，
         如果找不到，根据配置重试次数，每次间隔1秒
        :param widget: 模板图片路径
        :param rate: 相似度
        :param multiple: 是否返回匹配到的多个目标
        :param match_number: 图像识别重试次数
        :return: 坐标元组
        """
        if rate is None:
            rate = float(setting.IMAGE_RATE)
        try:
            for element in widget:
                for _ in range((match_number or int(setting.IMAGE_MATCH_NUMBER)) + 1):
                    locate = cls._match_image_by_opencv(
                        element, rate, multiple=multiple
                    )
                    if not locate:
                        sleep(int(setting.IMAGE_MATCH_WAIT_TIME))
                    else:
                        return locate
            raise TemplateElementNotFound(*widget)
        except Exception as e:
            raise e

    @staticmethod
    def find_image_color(widget):
        """
         获取图片的颜色值
        :param widget: 模板图片路径
        :return: 图片的颜色值
        """
        try:
            if not os.path.exists(widget):
                raise TemplatePictureNotExist(widget)
            _color = []
            with Image.open(widget) as im:
                pix = im.load()
                width = im.size[0]
                height = im.size[1]
                for x in range(width):
                    for y in range(height):
                        r, g, b = pix[x, y]
                        _color.append((r, g, b))
            return _color
        except Exception as e:
            raise e

    @classmethod
    def img_exists(cls, widget, rate=None):
        """
         判断图片是否存在，通常用于断言
        :param widget: 模块图片路径
        :param rate: 相似度
        :return:
        """
        if rate is None:
            rate = float(setting.IMAGE_RATE)
        try:
            return bool(cls.find_image(widget, rate=rate))
        except:
            return False

    @staticmethod
    def get_pic_px(pic_position):
        """
        获取图片的分辨率
        :param pic_position: 图片路径
        """
        return Image.open(os.path.expanduser(pic_position)).size


class ImageCenterByRGB:
    """
    By sliding and comparing the RGB values of small image and large image,
    locate the position of small image in large image.Some pre matching
    techniques are used to improve the speed.
    """

    @staticmethod
    def _check_match(_x, _y, small, bdata, sdata, rate):
        """
        Matching degree of small graph and large graph matching
        """
        same = 0
        diff = 0
        for i in range(small.width):
            for j in range(small.height):
                if bdata[_x + i, _y + j] == sdata[i, j]:
                    same = same + 1
                else:
                    diff = diff + 1
        similarity = same / (same + diff)
        return similarity >= rate

    @staticmethod
    def _pre_random_point(small):
        """
        Pre matching, take 10-20 points at random each time,
        and take coordinates randomly in the small graph
        """
        point_list = []
        count = random.randrange(10, 20)
        for _ in range(count):
            s_x = random.randrange(0, small.width)
            s_y = random.randrange(0, small.height)
            point_list.append([s_x, s_y])
        return point_list

    @staticmethod
    def _pre_random_match(_x, _y, point_list, bdata, sdata, rate):
        """
        In the small graph, several points are randomly
        selected for matching, and the matching degree is
        also set for the random points
        """
        same = 0
        diff = 0
        for point in point_list:
            if bdata[_x + point[0], _y + point[1]] == sdata[point[0], point[1]]:
                same = same + 1
            else:
                diff = diff + 1
        return same / (same + diff) >= rate

    @classmethod
    def image_center_by_rgb(cls, image_name=None, image_path=None, rate=setting.RATE):
        """
        By comparing the RGB values of the small image with the large
        image on the screen, the coordinates of the small image on
        the screen are returned.
        """
        if not image_path:
            image_path = setting.PIC_PATH
        small = Image.open(os.path.join(image_path, f"{image_name}.png"))
        sdata = small.load()
        big = pyscreenshot.grab()
        bdata = big.load()
        point_list = cls._pre_random_point(small)
        for _x in range(big.width - small.width):
            for _y in range(big.height - small.height):
                if cls._pre_random_match(_x, _y, point_list, bdata, sdata, rate):
                    if cls._check_match(_x, _y, small, bdata, sdata, rate):
                        return int(_x + small.width / 2), int(_y + small.height / 2)
        return False
