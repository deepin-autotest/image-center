import os

from image_center import ImageCenter

current_dir = os.path.dirname(os.path.abspath(__file__))


def test_client():
    res = ImageCenter.find_image(f"{current_dir}/test")
    assert res
