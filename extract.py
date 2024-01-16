#!/bin/bash
import re
import cv2
import pytesseract
from PIL import Image

# Set the path to the Tesseract executable (update it based on your installation)
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Function to preprocess and extract text from an image
def extract_text(image):
    # Increase contrast
    _, img = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY)

    # OCR using Tesseract
    text = pytesseract.image_to_string(Image.fromarray(img), lang='heb', config='--psm 11' )

    # Post-process text (customize as needed)
    text = re.sub(r'[^A-Za-z0-9א-ת\s\.,!?-]', '', text)

    return text.strip()
# Function to format milliseconds into "hh:mm:ss,SSS" format
def format_time(milliseconds):
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds}"

# Function to process video and generate SRT file
def process_video(video_path, output_srt):
    cap = cv2.VideoCapture(video_path)

    # Retrieve the frame count and duration
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(frame_count)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(fps)

    # Calculate the duration
    duration = frame_count / fps if fps > 0 else 0
    print(duration)

    # Check if the frame rate is zero
    if fps == 0:
        print("Error: Unable to determine frame rate. Please check the video file.")
        return

    # Get the screen height
    screen_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Initialize variables for subtitle tracking
    current_text = ''
    start_time = 0
    end_time = 0
    with open(output_srt, 'w', encoding='utf-8') as srt_file:
        for i in range(frame_count):
            ret, frame = cap.read()
            # Define region of interest for cropping
            roi = frame[screen_height-140:screen_height-90, 0:frame.shape[1]]
            # _, roi_thresh = cv2.threshold(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 200, 255, cv2.THRESH_BINARY_INV)
            _, roi_thresh = cv2.threshold(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 245, 255, cv2.THRESH_BINARY_INV)


            # Extract text from the region
            text = extract_text(roi_thresh)
            if text:  # Skip frames with no text
                if text == current_text:  # Extend duration if same text is detected
                    end_time = int(((i + 1) / fps) * 1000)
                else:  # Start a new subtitle entry
                    if current_text:
                        # Create the previous subtitle entry
                        srt_line = f'{i}\n{format_time(start_time)} --> {format_time(end_time)}\n{current_text}\n\n'

                        # Write the previous subtitle entry
                        srt_file.write(srt_line)
                        # Print the SRT line
                        print(srt_line)


                    # Update current subtitle variables
                    current_text = text
                    start_time = int((i / fps) * 1000)
                    end_time = int(((i + 1) / fps) * 1000)


            # Display image and OCR output
            cv2.imshow('Frame', roi_thresh)
            # print(f'Hebrew OCR: {text}\nSRT Line: {srt_line}\n')
            print(f'Hebrew OCR: {text}\n')

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        # Write the last subtitle entry
        if current_text:
            srt_file.write(f'{i+1}\n{format_time(start_time)} --> {format_time(end_time)}\n{current_text}\n\n')


    cap.release()
    cv2.destroyAllWindows()

# Example usage
video_path = '/home/uri/tmp/videos/Madrasa/Madrasa-S01E01-New-Begining.mp4'
output_srt = 'output.srt'
process_video(video_path, output_srt)

if __name__ == "__main__":
    pass
