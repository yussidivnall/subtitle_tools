#!/bin/bash
""" Exracts hardcoded Subtitles from a video using OCR """
import os
import re
import logging
import argparse
# from ast import literal_eval
import numexpr
import cv2
import pytesseract
from PIL import Image

# Set the path to the Tesseract executable (update it based on your installation)
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

config = {
    "language": "heb",
    "clip_region": {
        "x0": 0,
        "y0": "height-140",
        "x1": "width",
        "y1": "height-90"

    },
    "text_color_range": (240, 255)  # This is in grayscale color range.
}


def get_srt_entry(index: int, start_time: str, end_time: str, text: str) -> str:
    """ A helped to create a subtitle entry from parameters """
    text = repr(text)
    srt_line = f'{index}\n{start_time} --> {end_time}\n{text}\n\n'
    return srt_line


def get_crop_region(width, height):
    """ Retrive the cropping region containing the subtitles """
    logging.debug("Cropping width %s and height %s", width, height)
    ret = {}
    for k, v in config['clip_region'].items():
        if isinstance(v, str):
            ret[k] = numexpr.evaluate(v).item()
        elif isinstance(v, int):
            ret[k] = v
    logging.debug("Returning from get_crop_region with %s", ret)
    return ret


def crop(frame, region):
    """ Crop a region from a frame """
    roi = frame[region["y0"]:region["y1"], region["x0"]:region["x1"]]
    return roi

# Function to preprocess and extract text from an image


def extract_text(image):
    """ Extract text from an image """
    # Increase contrast
    _, img = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY)

    # OCR using Tesseract
    text = pytesseract.image_to_string(Image.fromarray(
        img), lang=config['language'], config='--psm 11')

    # Post-process text (customize as needed)
    text = re.sub(r'[^A-Za-z0-9א-ת\s\.,!?-]', '', text)

    return text.strip()


def get_output_filename(video_file: str) -> str:
    """ Get a default output file

    Args:
        video_file(str): A video file name
    Returns:
        str: video_file with extension changed to '.config["language"].srt
    """
    ret = os.path.splitext(video_file)[0]+f'.{config["language"]}.srt'
    return ret


# Function to format milliseconds into "hh:mm:ss,SSS" format
def format_time(milliseconds: int) -> str:
    """ Converts miliseconds to HH: MM: SS, Miliseconds """
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds}"

# Function to process video and generate SRT file


def process_video(video_path: str, output_srt: str, display: bool = True):
    """ Process a video and produce an srt file

    Args:
        video_path(str): A video to process
        output_srt(str): an srt file to create
        display(bool): if False don't show the image
    """
    cap = cv2.VideoCapture(video_path)

    # Retrieve the frame count and duration
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = frame_count / fps if fps > 0 else 0
    logging.debug(
        "processing %s frames at %s fps. duration: %s minutes", frame_count, fps, duration/60)

    if duration == 0:
        err_message = f"Unable to determine duration of {video_path} {duration} frames at {fps} fps"
        logging.error(err_message)
        raise ValueError(err_message)
    # Get the screen height
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    crop_region = get_crop_region(frame_width, frame_height)
    text_color_range = config['text_color_range']
    logging.debug('cropping: %s', crop_region)
    logging.debug('range: %s', config["text_color_range"])
    # Initialize variables for subtitle tracking
    idx = 0
    current_text = ''
    start_time = 0
    end_time = 0
    with open(output_srt, 'w', encoding='utf-8') as srt_file:
        for i in range(frame_count):
            _, frame = cap.read()
            # Define region of interest for cropping
            # roi = frame[frame_height-140:frame_height-90, 0:frame_width]
            roi = crop(frame, crop_region)
            _, roi_thresh = cv2.threshold(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY),
                                          text_color_range[0],
                                          text_color_range[1],
                                          cv2.THRESH_BINARY_INV)

            # Extract text from the region
            text = extract_text(roi_thresh)
            if text:  # Skip frames with no text
                if text == current_text:  # Extend duration if same text is detected
                    end_time = int(((i + 1) / fps) * 1000)
                else:  # Start a new subtitle entry
                    if current_text:
                        # Create the previous subtitle entry
                        idx += 1
                        srt_line = get_srt_entry(
                            idx, format_time(start_time), format_time(end_time), current_text)
                        logging.debug(srt_line)
                        # Write the previous subtitle entry
                        srt_file.write(srt_line)

                    # Update current subtitle variables
                    current_text = text
                    start_time = int((i / fps) * 1000)
                    end_time = int(((i + 1) / fps) * 1000)

            current_time = int((i / fps) * 1000)
            print(f'{ current_time/60/60 }: {text}')
            # Display image and OCR output
            if display:
                cv2.imshow('Frame', roi_thresh)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        # Write the last subtitle entry
        if current_text:
            srt_line = get_srt_entry(
                idx, format_time(start_time), format_time(end_time), current_text)
            srt_file.write(srt_line)

    cap.release()
    cv2.destroyAllWindows()


def main():
    """ Main Function(but pylint demands docstring """
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(
        description='Extracts hardcoded subtitles from a video')
    parser.add_argument('video', help='A video file to extract subtitles from')
    parser.add_argument(
        '--output', "-o", help='A video file to extract subtitles from')
    parser.add_argument("--dont-display", "-d",
                        action='store_true', help="Dont display the OCR image")
    args = parser.parse_args()
    video_path = args.video
    dont_display = args.dont_display
    logging.info("Processing video %s", video_path)
    if args.output:
        output_srt = args.output
    else:
        output_srt = get_output_filename(video_path)
    logging.info("Saving to %s", output_srt)
    process_video(video_path, output_srt, display=not dont_display)


if __name__ == "__main__":
    main()
