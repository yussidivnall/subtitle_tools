#!/bin/python
""" Attempts to fix a polluted srt subtitle file """
import io
import os
import sys
import re
import logging
import subprocess
import argparse
import csv
import Levenshtein
from fuzzywuzzy import fuzz
import argcomplete

# A Levenshtein similarity score,
# two strings below this distance
# are considered "similar"
SIMILARITY_CUTOFF = 0.5

config = {
    "delete_list": [],
    "threshold": 0.5
}


def clean_text(text: str) -> str:
    """ Remove special charecters from text """
    ret = text.replace("\\n", "").replace("\\t", "")
    return ret


def get_srt_entry(index: int, start_time: str, end_time: str, text: str) -> str:
    """ A helper to create a subtitle entry from parameters """
    srt_line = f'{index}\n{start_time} --> {end_time}\n{text}\n\n'
    return srt_line


def load_srt(input_srt: str) -> list:
    """ Load a .srt file

    Args:
        input_srt(str): an srt file
    Returns:
        list[{start_time, end_time, text, action: 'do nothing'}, {...}, ...]
    """
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


def csv_safe(string: str) -> str:
    """ Format string to be a safe CSV text"""
    outstream = io.StringIO()   # "fake" output file
    cw = csv.writer(outstream)  # pass the fake file to csv module
    cw.writerow([string])       # write a row
    return outstream.getvalue()  # get the contents of the fake file


def save_actions(subtitles, output_csv):
    """ Save proposed actions to a CSV to be used to generate a new .srt file """
    # Create a list to store rows for the CSV file
    csv_rows = [['start_time', 'end_time', 'action', 'text']]

    # Populate the list with subtitle information
    for subtitle in subtitles:
        # Escape CSV delimiter in text
        start_time = subtitle['start-time']
        end_time = subtitle['end-time']
        action = subtitle['action']
        text = subtitle['text']
        entry = [start_time, end_time, action, text]
        csv_rows.append(entry)

    # Save the list to a CSV file
    with open(output_csv, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',')
        csv_writer.writerows(csv_rows)


def guess_sentence(sentences: list[str]) -> str | None:
    """ Try to guess the correct sentence from a list of probably incorrect sentences

    Args:
        sentences(list[str]): list of strings with a similar sentence
    Returns(str|None): best guess or None
    """

    print("Sentences to try and guess: ", sentences)
    original_sentence = None
    max_similarity = 0

    for i, sentence1 in enumerate(sentences):
        similarity_sum = 0

        for j, sentence2 in enumerate(sentences):
            if i != j:  # Avoid comparing the same sentence
                # Calculate similarity using fuzz ratio
                similarity_sum += fuzz.ratio(sentence1, sentence2)

        # Average similarity across all comparisons
        average_similarity = similarity_sum / (len(sentences) - 1)

        if average_similarity > max_similarity:
            max_similarity = average_similarity
            original_sentence = sentence1

    return original_sentence


def is_garbage(text: str, delete_list: list) -> bool:
    """ Try and guess if text is garbage

    Args:
        text(str): The text to check
        delete_list(list[regex]): A list of regular expresisons,
            when text matches an entry in delete_list consider it garbage
    """
    # Add your criteria for identifying garbage text
    if delete_list:
        for d in delete_list:
            if d.search(text):
                return True
    if len(text) < 3 or text.isdigit() or text.strip() == "1":
        return True
    return False


def normalized_levenshtein_distance(str1: str, str2: str) -> float:
    """ Returns a Levenshtein distance score normalised by string length

    Args:
        str1(str): String A
        str2(str): String B
    Returns(float): The Levenshtein score
    """
    len_max = max(len(str1), len(str2))
    if len_max == 0:
        return 0  # Both strings are empty, consider them similar

    distance = Levenshtein.distance(str1, str2)
    ret = distance / len_max
    logging.debug("\"%s\" is similar to \"%s\" by %s", str1, str2, ret)
    return ret


def is_similar(prev_text: str, current_text: str, cutoff: float = SIMILARITY_CUTOFF) -> bool:
    """ Decide if two strings are similar enought to suggest merge """
    if normalized_levenshtein_distance(prev_text, current_text) <= cutoff:
        logging.debug("merge %s", current_text)
        return True
    return False


def edit_actions(actions_file: str):
    """ Helped to open action file in user's text editor """
    editor_command = os.environ.get('EDITOR', 'vim')
    subprocess.run([editor_command, actions_file], check=True)


def apply_actions(actions_csv_file: str, output_srt_file: str):
    """ Apply actions in actions in action_csv_file to create output_srt file"""
    # Load actions from the CSV file
    actions = []
    with open(actions_csv_file, 'r', encoding='utf-8') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            actions.append(row)

    # Generate SRT content based on actions
    srt_content = []
    current_subtitle = {'start-time': '', 'end-time': '', 'text': ''}

    for action in actions:
        print("action: ", action)
        if action['action'] == 'delete':
            # Skip this entry if action is 'delete'
            continue
        elif action['action'] == 'merge':
            # Set the end time of the last subtitle to be the current subtitle's end time
            # current_subtitle['end-time'] = action['end_time']
            continue
        else:
            # On 'do nothing' and 'merge to'
            # Save the current subtitle to the SRT content list
            if current_subtitle['start-time'] != '':
                srt_content.append(get_srt_entry(
                    len(srt_content)+1,
                    current_subtitle["start-time"],
                    current_subtitle["end-time"],
                    current_subtitle["text"]))

            # Update current_subtitle with the current action
            current_subtitle['start-time'] = action['start_time']
            current_subtitle['end-time'] = action['end_time']
            current_subtitle['text'] = action['text']

    # Save the last subtitle to the SRT content list
    srt_content.append(f"{len(srt_content) + 1}\n"
                       f"{current_subtitle['start-time']} --> {current_subtitle['end-time']}\n"
                       f"{current_subtitle['text']}\n\n")

    # Write the SRT content to the output SRT file
    with open(output_srt_file, 'w', encoding='utf-8') as srt_file:
        srt_file.writelines(srt_content)


def process_subtitles(subtitle_action_list: list, delete_list: list, similarity: float) -> list:
    """ Process a subtitle action list, populates actions """
    ret = []
    if delete_list is None:
        delete_list = []
    else:
        delete_list = [re.compile(r) for r in delete_list]

    merging = False  # Keeps track of wether we are inside a merge operation
    merging_list = []
    mergins_start_time = ""
    prev_subtitle = {}
    # for i, subtitle in enumerate(subtitle_action_list):
    for subtitle in subtitle_action_list:
        subtitle['text'] = clean_text(subtitle['text'])
        ret.append(subtitle)
        # Decide on an action, `merge`, 'delete' or 'do nothing'
        if is_garbage(subtitle['text'], delete_list):
            logging.debug("delete: %s", subtitle["text"])
            subtitle['action'] = 'delete'
            continue
        if prev_subtitle and is_similar(prev_subtitle['text'], subtitle['text'], similarity):
            # This is the start of a merging sequence
            if not merging:
                merging = True
                mergins_start_time = prev_subtitle['start-time']
                prev_subtitle['action'] = 'merge'
                merging_list.append(prev_subtitle['text'])
            merging_list.append(subtitle["text"])
            subtitle['action'] = 'merge'

        # Ending merge sequence
        if subtitle['action'] == 'do nothing' and merging:
            merging = False
            guess = guess_sentence(merging_list)
            merging_entry = {
                "start-time": mergins_start_time,
                "end-time": subtitle["end-time"],
                "action": "merge to",
                "text": guess
            }
            ret.insert(-1, merging_entry)
            merging_list = []
        prev_subtitle = subtitle
    return ret


def parse_args():
    """ Parse Command line arguments """
    parser = argparse.ArgumentParser(
        description='Load and process SRT files.\n ')
    parser.add_argument("srt_file")
    parser.add_argument(
        '--output_srt_file', help='Path to the output SRT file, defaults to overwrite input srt')
    parser.add_argument("--threshold", default=config["threshold"], type=float,
                        help="A Levenshtien distance score, normalised by subtitle lengths, used for merging")
    parser.add_argument("--delete", nargs="+", type=str,
                        help="Regular expressions to delete, subtitles matching this will be removed")
    parser.add_argument("--confirm", action='store_true',
                        help="Don't open editor just apply actions")
    parser.add_argument("--apply-actions-csv", "-a", type=str,
                        help="apply an existing actions csv and exit")
    parser.add_argument("--dont-apply", action='store_true',
                        help="Don't apply, only generate actionable CSV file")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    return args


def main():
    """ Main, no a lot more to say but pylint insists i say something """

    args = parse_args()
    srt_file = args.srt_file
    output_srt_file = args.output_srt_file
    apply_actions_csv = args.apply_actions_csv
    dont_apply = args.dont_apply

    if not output_srt_file:
        output_srt_file = srt_file

    if apply_actions_csv:
        # Apply actionable list csv, no need to generate one
        apply_actions(apply_actions_csv, output_srt_file)
        sys.exit(0)

    action_csv_file = output_srt_file+".actions.csv"
    subtitles = load_srt(srt_file)
    subtitles = process_subtitles(
        subtitles,
        delete_list=args.delete,
        similarity=args.threshold)
    save_actions(subtitles=subtitles, output_csv=action_csv_file)
    if not args.confirm:
        choice = input("Created actionable list [C]confirm, [i]nspect.")
        if choice == 'i':
            edit_actions(action_csv_file)
            save = input("Apply changes? [Y]es, [n]o")
            if save == 'n':
                dont_apply = True
                logging.info("Not saving %s, actions written to %s",
                             output_srt_file, action_csv_file)
                logging.info("To apply action file use `python ./extract.py --apply-actions-csv %s %s",
                             action_csv_file, output_srt_file)

    # Save srt file
    if not dont_apply:
        apply_actions(action_csv_file, output_srt_file)
        logging.info("%s written", output_srt_file)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
