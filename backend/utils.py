import cv2
import base64
import numpy as np


def get_first_frame_from_video(video_path):
    """
    Extracts and returns the first frame from a video file.

    Parameters:
        video_path (str): The file path to the video.

    Returns:
        numpy.ndarray: The first frame of the video in BGR format (as read by OpenCV),
                       or None if the video could not be read.

    Raises:
        FileNotFoundError: If the video file does not exist.
        ValueError: If the video cannot be opened or the first frame cannot be read.
    """
    # Check if the file exists
    if not isinstance(video_path, str) or not video_path:
        raise ValueError("The video path must be a valid, non-empty string.")

    # Open the video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video file: {video_path}")

    # Read the first frame
    success, frame = cap.read()
    cap.release()  # Release the video file

    if not success:
        raise ValueError("Failed to read the first frame from the video.")

    return frame


def encode_image(image):
    """
    Encodes an image to a base64 string with a data URL prefix.

    Parameters:
        image (numpy.ndarray): The image to encode, typically read by OpenCV (in BGR format).

    Returns:
        str: A base64-encoded string representing the image, prefixed with "data:image/jpg;base64,".

    Raises:
        ValueError: If the image encoding fails or the input is not a valid numpy array.
    """
    if not isinstance(image, np.ndarray):
        raise ValueError("Input image must be a numpy array.")

    # Encode the image to JPEG format
    success, buffer = cv2.imencode('.jpg', image)
    if not success:
        raise ValueError("Image encoding failed.")

    # Convert the encoded image to base64
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpg;base64,{base64_str}"


def decode_image(encoded_img_str):
    """
    Decodes a base64-encoded image string back into an OpenCV image (numpy array).

    Parameters:
        encoded_img_str (str): The base64 string representing the image.
                               It should include the "data:image/jpg;base64," prefix.

    Returns:
        numpy.ndarray: The decoded image in BGR format suitable for OpenCV processing.

    Raises:
        ValueError: If decoding fails due to an invalid base64 string or incompatible data.
    """
    if not isinstance(encoded_img_str, str):
        raise ValueError("Encoded image must be a string.")

    # Remove the data URL prefix if present
    if encoded_img_str.startswith("data:image"):
        encoded_img_str = encoded_img_str.split(',', 1)[1]

    try:
        # Decode the base64 string to bytes
        encoded_img_bytes = base64.b64decode(encoded_img_str)
        # Convert bytes to a numpy array and decode to an OpenCV image
        decoded_img = cv2.imdecode(np.frombuffer(encoded_img_bytes, np.uint8), cv2.IMREAD_COLOR)
        if decoded_img is None:
            raise ValueError("Image decoding failed; data may be corrupt or incompatible.")
        return decoded_img
    except (base64.binascii.Error, ValueError) as e:
        raise ValueError("Invalid base64 string or incompatible image data.") from e


def draw_bboxes(frame, bboxes):
    """
    Draws bounding boxes on an image frame.

    Parameters:
        frame (numpy.ndarray): The image on which to draw the bounding boxes, typically in BGR format.
        bboxes (list of tuples): A list of bounding box coordinates, where each bounding box is defined
                                 as (x_min, y_min, x_max, y_max) in pixel values.

    Returns:
        numpy.ndarray: The modified frame with bounding boxes drawn.

    Raises:
        ValueError: If `frame` is not a numpy array or if `bboxes` is not a list of valid tuples.
    """
    if not isinstance(frame, np.ndarray):
        raise ValueError("Input frame must be a numpy array.")

    if not isinstance(bboxes, list) or not all(isinstance(box, (tuple, list)) and len(box) == 4 for box in bboxes):
        raise ValueError(
            "Bounding boxes must be a list of tuples or a list of list "
            "with four numeric values (x_min, y_min, x_max, y_max).")

    for (x_min, y_min, x_max, y_max) in bboxes:
        # Ensure bounding box coordinates are valid integers
        try:
            x_min, y_min, x_max, y_max = map(int, (x_min, y_min, x_max, y_max))
        except (TypeError, ValueError):
            raise ValueError("Bounding box coordinates must be convertible to integers.")

        # Check if the bounding box coordinates are within frame dimensions
        if not (0 <= x_min < x_max <= frame.shape[1]) or not (0 <= y_min < y_max <= frame.shape[0]):
            raise ValueError(f"Bounding box coordinates ({x_min}, {y_min}, {x_max}, {y_max}) are out of frame bounds.")

        # Draw the rectangle on the frame
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 4)

    return frame
