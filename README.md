# image-center
图像识别定位某个元素在当前屏幕中的坐标；

在自动化测试中获取到元素坐标之后，可以传入到键鼠工具，从而实现对目标元素的操作。

---

**Documentation**: <a href="https://funny-test.github.io/image-center" target="_blank">https://funny-test.github.io/image-center</a>

**Source Code**: <a href="https://github.com/funny-test/image-center" target="_blank">https://github.com/funny-test/image-center</a>

---

## 安装

```console
pip install image-center
```

## 使用说明

截取目标元素图片，将图片保存到某个路径；

```python
from image_center import ImageCenter

ImageCenter.find_image("~/Desktop/test.png")
```

返回 `test.png` 在当前屏幕中的位置。
