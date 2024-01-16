# Subtitle Tools
A collection of utilities to simplify creation of subtitles for videos

# Extract
## extract.py
This is a utility to extract hardcoded subtitles from a video containing subtitles. it uses Tesseeract to perform Optical Charecter Recognition (OCR).
It works by defining a box region on the screen containing the subtitles, and filtering out a colour theshold of the subtitles to remove as much noise as possible.

# Fix
## fix_srt.py
This utility tries to improve on the results obtained by the OCR. It creates an editable action list for every subtitle entry.
Actions can include "do nothing", "delete" and "merge"

- "do nothing": this action leaves the subtitle entry in it's place and is the default action
- "delete": this action removed the subtitle. `fix_srt.py` performs a basic garbage detection. 
            currently this checks if the subtitle is less then 3 charecters long or is a digit.
- "merge": this action decides if to merge consequative subtitles into one based on similarity.
           it performs a normalised Levenshtein distance to determine that by comparing the subtitle 
           to the previous one. if it thinks it's close enough it will merge their timing together into one.
           The last subtitle with the action "do nothing" will be extended to match the end_time of the last
           subtitle with "merge" action in the sequance.


The list is then displayed to the user for inspection and modification and a new .srt subtitles file is produced.
The user can then change the action or fix the subtitle text. note that to "delete" you can either set the action (third column) to "delete" or simply delete the line from the acitonable list. "merge" will merge to the last "do nothing" entry so you can just fix that one if it is incorrect.

You might need to perform this multiple times, perhaps with different Levenshtein values.
