import os
import subprocess
import argparse
import csv
import Levenshtein

# A Levenshtein similarity score, 
# two strings below this distance
# are considered "similar"
SIMILARITY_CUTOFF = 0.12

def load_srt(input_srt):
    subtitles = []

    with open(input_srt, 'r', encoding='utf-8') as srt_file:
        lines = srt_file.read().splitlines()

    index = 0

    while index < len(lines):
        if lines[index].isdigit():
            index += 1  # Skip subtitle index
            time_range = lines[index]
            if '-->' not in time_range:
                # Skip incomplete or unexpected data
                index += 1
                continue

            start_time, end_time = map(str.strip, time_range.split('-->'))
            index += 1  # Move to the next line containing text
            text = []
            while index < len(lines) and lines[index]:
                text.append(lines[index])
                index += 1
            subtitles.append({
                'start-time': start_time,
                'end-time': end_time,
                'text': ' '.join(text),
                'action': 'do nothing'
            })

        index += 1  # Move to the next subtitle

    return subtitles

def save_actions(subtitles, output_csv):
    # Create a list to store rows for the CSV file
    csv_rows = [['start_time', 'end_time', 'action', 'text']]

    # Populate the list with subtitle information
    for subtitle in subtitles:
        csv_rows.append([subtitle['start-time'], subtitle['end-time'], subtitle['action'], subtitle['text']])

    # Save the list to a CSV file
    with open(output_csv, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerows(csv_rows)



def is_garbage(text):
    # Add your criteria for identifying garbage text
    if len(text) < 3 or text.isdigit() or text.strip() == "1":
        return True
    return False

def normalized_levenshtein_distance(str1, str2):
    len_max = max(len(str1), len(str2))
    if len_max == 0:
        return 0  # Both strings are empty, consider them similar
    else:
        distance = Levenshtein.distance(str1, str2)
        ret = distance / len_max
        print(f'"{str1}" =~ "{str2}" by {ret}')
        return ret


def is_similar(prev_text, current_text):
    if normalized_levenshtein_distance(prev_text,current_text) <= SIMILARITY_CUTOFF:
        print("Similar")
        return True
    return False

def edit_actions(actions_file):
    # Open the CSV file in the user's preferred text editor
    editor_command = os.environ.get('EDITOR', 'vim')  # Default to 'vim' if EDITOR is not set
    subprocess.run([editor_command, actions_file])

def apply_actions(actions_file, output_srt):
    # Load actions from the CSV file
    actions = []
    with open(actions_file, 'r', encoding='utf-8') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            actions.append(row)

    # Generate SRT content based on actions
    srt_content = []
    current_subtitle = {'start-time': '', 'end-time': '', 'text': ''}

    for action in actions:
        if action['action'] == 'delete':
            # Skip this entry if action is 'delete'
            continue

        if action['action'] == 'merge':
            # Set the end time of the last subtitle to be the current subtitle's end time
            current_subtitle['end-time'] = action['end_time']
        else:
            # Save the current subtitle to the SRT content list
            if current_subtitle['start-time'] != '':
                srt_content.append(f"{len(srt_content) + 1}\n"
                                   f"{current_subtitle['start-time']} --> {current_subtitle['end-time']}\n"
                                   f"{current_subtitle['text']}\n\n")

            # Update current_subtitle with the current action
            current_subtitle['start-time'] = action['start_time']
            current_subtitle['end-time'] = action['end_time']
            current_subtitle['text'] = action['text']

    # Save the last subtitle to the SRT content list
    srt_content.append(f"{len(srt_content) + 1}\n"
                       f"{current_subtitle['start-time']} --> {current_subtitle['end-time']}\n"
                       f"{current_subtitle['text']}\n\n")

    # Write the SRT content to the output SRT file
    with open(output_srt, 'w', encoding='utf-8') as srt_file:
        srt_file.writelines(srt_content)



def main():
    parser = argparse.ArgumentParser(description='Load and process SRT files.')
    parser.add_argument('--input_srt_file', help='Path to the input SRT file')
    parser.add_argument('--output_srt_file', help='Path to the output SRT file (optional)')
    parser.add_argument("--similarity-threshold", default=SIMILARITY_CUTOFF, type=float, help="A Levenshtien distance score, normalised by subtitle lengths")
    parser.add_argument("--delete", nargs="+", type=str, help="A regular expressions to delete, subtitles matching this will be removed")

    args = parser.parse_args()

    input_srt = args.input_srt_file
    output_srt = args.output_srt_file

    subtitles = load_srt(input_srt)

    prev_subtitle = None
    for i, subtitle in enumerate(subtitles):
        if is_garbage(subtitle['text']):
            print(f"Garbage text detected! Action: delete")
            # Decide on an action, e.g., 'delete' or 'do nothing'
            subtitle['action'] = 'delete'
            continue
        if prev_subtitle and is_similar(prev_subtitle['text'],subtitle['text']):
            subtitle['action'] = 'merge'
        prev_subtitle = subtitle
        #print(f"Start Time: {subtitle['start-time']}, End Time: {subtitle['end-time']}")
        #print(f"Text: {subtitle['text']}, Action: {subtitle['action']}")
        #print()

    save_actions(subtitles=subtitles, output_csv="actions.csv")
    edit_actions("actions.csv")

    if output_srt:
        apply_actions("actions.csv", output_srt)

if __name__ == "__main__":
    main()

