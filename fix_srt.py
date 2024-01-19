import os
import re
import logging
import subprocess
import argparse
import csv
import Levenshtein

# A Levenshtein similarity score, 
# two strings below this distance
# are considered "similar"
SIMILARITY_CUTOFF = 0.2

def load_srt(input_srt) -> list:
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



def is_garbage(text, delete_list):
    # Add your criteria for identifying garbage text
    if delete_list:
        for d in delete_list:
            if (d.search(text)):
                return True
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
        logging.debug(f"\"{str1}\" is similar to \"{str2}\" by {ret}")
        return ret


def is_similar(prev_text, current_text, cutoff = SIMILARITY_CUTOFF):
    if normalized_levenshtein_distance(prev_text,current_text) <= cutoff:
        logging.debug(f"merge {current_text}")
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
    parser = argparse.ArgumentParser(description='Load and process SRT files.\n ')
    parser.add_argument("srt_file")
    parser.add_argument('--output_srt_file', help='Path to the output SRT file, defaults to overwrite input srt')
    parser.add_argument("--threshold", default=SIMILARITY_CUTOFF, type=float, help="A Levenshtien distance score, normalised by subtitle lengths, used for merging")
    parser.add_argument("--delete", nargs="+", type=str, help="Regular expressions to delete, subtitles matching this will be removed")
    parser.add_argument("--confirm", action='store_true', help="Don't open editor just apply actions")
    parser.add_argument("--apply-actions-csv", "-a", type=str, help = "apply an existing actions csv and exit")
    parser.add_argument("--dont-apply", action='store_true', help="Don't apply, only generate actionable CSV file")

    args = parser.parse_args()
    srt_file = args.srt_file
    output_srt = args.output_srt_file
    del_list = args.delete
    similarity = args.threshold
    confirm = args.confirm
    apply_actions_csv = args.apply_actions_csv
    dont_apply = args.dont_apply

    if not output_srt:
        output_srt = srt_file

    if apply_actions_csv:
        # Apply actionable list csv, no need to generate one
        apply_actions(apply_actions_csv, output_srt)
        exit(0)

    action_csv_file = output_srt+".actions.csv"

    if del_list is None:
        delete_list = []
    else:
        delete_list = [ re.compile(r) for r in del_list ]

    subtitles = load_srt(srt_file)

    prev_subtitle = None
    for i, subtitle in enumerate(subtitles):
        # Decide on an action, `merge`, 'delete' or 'do nothing'
        if is_garbage(subtitle['text'], delete_list):
            logging.debug(f'delete: {subtitle["text"]}')
            subtitle['action'] = 'delete'
            continue
        if prev_subtitle and is_similar(prev_subtitle['text'],subtitle['text'], similarity):
            subtitle['action'] = 'merge'

        prev_subtitle = subtitle

    save_actions(subtitles=subtitles, output_csv=action_csv_file)
    if not confirm:
        choice = input("Created actionable list [A]pply, [i]nspect.")
        if choice == 'i':
            edit_actions(action_csv_file)

    # Save srt file
    if not dont_apply:
        apply_actions(action_csv_file, output_srt)
        logging.info(f"{output_srt} written")

if __name__ == "__main__":
    logging.basicConfig(level = logging.DEBUG)
    main()
