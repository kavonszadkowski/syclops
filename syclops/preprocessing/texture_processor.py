from pathlib import Path

import cv2
import numpy as np
import ruamel.yaml as yaml
from perlin_numpy import generate_fractal_noise_2d, generate_perlin_noise_2d


def read_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        yaml_dict = yaml.safe_load(f)
    if "textures" in yaml_dict:
        return yaml_dict["textures"]
    else:
        return None


def perlin(texture: np.ndarray, config: dict, textures: dict, current_frame: int):
    """Generate Perlin Noise"""
    res = config["res"]
    octaves = config["octaves"]
    texture = generate_fractal_noise_2d(
        shape=texture.shape, res=(res, res), octaves=octaves
    )
    texture = (texture + 1) / 2
    # Clip the texture to 0-1
    texture = np.clip(texture, 0, 1)
    return texture


def math_expression(
    texture: np.ndarray, config: dict, textures: dict, current_frame: int
):
    x = texture
    # Temporarily create variables from textures dict
    for texture_name, texture in textures.items():
        frame_id = current_frame % len(texture)
        # Resize texture to match the current texture
        texture = cv2.resize(texture[frame_id], (x.shape[1], x.shape[0]))
        globals()[texture_name] = texture
    return eval(config).astype(x.dtype)


def input_texture(
    texture: np.ndarray, config: dict, textures: dict, current_frame: int
):
    """Input a texture from the textures dict"""
    frame_id = current_frame % len(textures[config])
    return cv2.resize(textures[config][frame_id], (texture.shape[1], texture.shape[0]))


def erode(texture: np.ndarray, config: dict, textures: dict, current_frame: int):
    """Erode the texture"""
    kernel = np.ones((config["kernel_size"], config["kernel_size"]), np.uint8)
    return cv2.erode(texture, kernel, iterations=config["iterations"])


def dilate(texture: np.ndarray, config: dict, textures: dict, current_frame: int):
    """Dilate the texture"""
    kernel = np.ones((config["kernel_size"], config["kernel_size"]), np.uint8)
    return cv2.dilate(texture, kernel, iterations=config["iterations"])


def clip(texture: np.ndarray, config: dict, textures: dict, current_frame: int):
    """Clip values outside min/max"""
    return np.clip(texture, config[0], config[1])


def blur(texture: np.ndarray, config: dict, textures: dict, current_frame: int):
    return cv2.GaussianBlur(texture, (config["kernel_size"], config["kernel_size"]), 0)


def contrast(texture: np.ndarray, config: dict, textures: dict, current_frame: int):
    adjusted_image = ((texture - 0.5)) * config + 0.5
    adjusted_image = np.clip(adjusted_image, 0, 1)

    return adjusted_image


def identical_contours(contour1, contour2):
    if len(contour1) == len(contour2):
        for i in range(len(contour1)):
            if (
                contour1[i][0][0] != contour2[i][0][0]
                or contour1[i][0][1] != contour2[i][0][1]
            ):
                return False
        else:
            return True
    else:
        return False


def keep_overlapp(
    texture: np.ndarray, config: dict, textures: dict, current_frame: int
):
    """Keep only areas that overlap with the other image"""
    other_texture = textures[config["texture"]][
        current_frame % len(textures[config["texture"]])
    ]
    other_texture = cv2.resize(other_texture, (texture.shape[1], texture.shape[0]))
    # Make both textures binary
    texture = (texture > 0.5).astype(np.uint8)
    other_texture = (other_texture > 0.5).astype(np.uint8)
    contours1, _ = cv2.findContours(texture, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours2, _ = cv2.findContours(
        other_texture, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # Merge textures and recalculate contours
    combined_texture = cv2.bitwise_or(texture, other_texture)
    combined_contours, _ = cv2.findContours(
        combined_texture, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # Find the contours that are in combined_contours but not in contours1 or contours2
    contours_to_keep = []
    for contour in combined_contours:
        found_identical_contour = False
        for contour1 in contours1:
            if identical_contours(contour, contour1):
                found_identical_contour = True
        for contour2 in contours2:
            if identical_contours(contour, contour2):
                found_identical_contour = True
        if not found_identical_contour:
            contours_to_keep.append(contour)

    # Create a mask from the contours
    mask = np.zeros_like(combined_texture)
    cv2.drawContours(mask, contours_to_keep, -1, 255, -1)
    mask = cv2.bitwise_and(mask, combined_texture * 255)
    return mask / 255


def random_rectangles(
    texture: np.ndarray, config: dict, textures: dict, current_frame: int
):
    """
    Draw random rectangles onto the texture
    """

    # Loop through each rectangle to be drawn
    for i in range(config["num_rectangles"]):
        # Randomly generate the dimensions of the rectangle
        width = int(np.random.normal(config["avg_width"], config["std_width"]))
        height = int(np.random.normal(config["avg_height"], config["std_height"]))

        # Randomly generate the center point of the rectangle
        cx = np.random.randint(width // 2, texture.shape[1] - width // 2)
        cy = np.random.randint(height // 2, texture.shape[0] - height // 2)

        # Randomly generate the rotation angle of the rectangle
        angle = np.random.randint(0, 360)

        # Generate the rectangle as a rotated box
        rect = cv2.boxPoints(((cx, cy), (width, height), angle))

        # Draw the rectangle onto the image
        cv2.drawContours(texture, [np.int0(rect)], 0, 255, thickness=-1)

    return texture / 255


def process_texture(tex_name: str, tex_dict: dict, textures: dict, current_frame: int):
    # Create Texture
    image_size = tex_dict["config"]["image_size"]
    texture = np.zeros((image_size[0], image_size[1]), np.float32)

    # Set numpy seed
    if "seed" in tex_dict["config"]:
        np.random.seed(tex_dict["config"]["seed"])

    for operation in tex_dict["ops"]:
        operation_name = list(operation.keys())[0]
        operation_conf = operation[operation_name]
        texture = globals()[operation_name](
            texture, operation_conf, textures, current_frame
        )
    return texture
