"""
Problem: all the EXIF data of photos is blank, meaning if I just shove all my
photos onto google images, it'll be in the wrong place in the timeline.

Solution: match each photo with when it was posted, and then edit the EXIF data
to match.
"""
import os
import json
from dataclasses import dataclass
from typing import Any
import piexif
import datetime
from datetime import datetime as DateTime

URI_ROOT = "facebook_data/"
POSTS_DIR = "facebook_data/your_activity_across_facebook/posts"
ALBUM_DIR = POSTS_DIR + "/album"
POSTS_AND_CHECKINS = "facebook_data/your_activity_across_facebook/posts/your_posts__check_ins__photos_and_videos_1.json"
UNCATEGORIZED_PHOTOS = (
    "facebook_data/your_activity_across_facebook/posts/your_uncategorized_photos.json"
)
MESSAGES_DIR = "facebook_data/your_activity_across_facebook/messages"
INBOX_DIR = MESSAGES_DIR + "/inbox"
ARCHIVED_DIR = MESSAGES_DIR + "/archived_threads"


@dataclass
class Photo:
    uri: str
    timestamp: int

    @classmethod
    def from_json_structure(cls, structure: dict):
        """
        The JSON structure for a photo is shared between messages, posts, and
        albums (and perhaps elsewhere).  The structure can contain a few things,
        but we're just interested in the URI (the location of the image,
        starting with "your_activity_across_facebook/") and the
        "creation_timestamp", which is the upload date. There is also
        (optionally) exif data, in "media_metadata" -> "photo_metadata" ->
        "exif_data". "media_metadata" itself is optional, as well.

        This "exif_data" key points to a list, oddly enough, although I never
        saw more than one dictionary in the list. The dictionary can contain
        various bits of data, but we're only interested in "taken_timestamp".
        Whenever the taken_timestamp is available, we want to use that instead
        of the creation_timestamp.
        """
        uri = structure["uri"]
        timestamp = (
            structure.get("media_metadata", {})
            .get("photo_metadata", {})
            .get("exif_data", [{}])[0]
            .get("taken_timestamp")
        )
        if timestamp is None:
            timestamp = structure["creation_timestamp"]

        return cls(uri, timestamp)


def get_photos_from_album(album_dir: str) -> list[Photo]:
    """
    In album_dir, there are multiple JSON files, named like 0.jons, 1.json, etc.
    Each JSON file represents one album. The file contains some album metadata,
    like the name and cover photo, but all we're interested in is the "photos"
    key, which is a list of all photos.
    """
    # Initialize a list to keep track of all json files in the directory
    json_files = [f for f in os.listdir(album_dir) if f.endswith(".json")]

    # Initialize an empty dict for the merged data
    photos: list[Photo] = []

    for file_name in json_files:
        file_path = os.path.join(album_dir, file_name)
        with open(file_path, "r") as file:
            data = json.load(file)

        extracted = extract_photos_from_list(data["photos"])
        photos.extend(extracted)

    return photos


def extract_photos_from_list(photos_data: list[dict]) -> list[Photo]:
    """
    `photos_data` is a list of dictionaries containing information about each
    photo. See documentation for `Photo.from_json_structure()`.

    Returns a list of all photos.
    """
    photos: list[Photo] = []

    for photo in photos_data:
        p = Photo.from_json_structure(photo)
        photos.append(p)

    return photos


def extract_photos_from_posts(data: list[dict]) -> list[Photo]:
    """
    This file is a bit different than the others. Each item in the `data` list
    corresponds to a single post. A single post can have multiple image
    attachments. The images are located at "attachments" (a list of dicts),
    then "data" (another list of dicts), then "media", which is the photo
    information in the same dictionary structure as used for albums and
    uncategorized photos.

    Returns a list of photos.
    """
    photos: list[Photo] = []

    for photo in data:
        data_section: list[dict] = photo.get("attachments", [{}])[0].get("data", [{}])
        for entry in data_section:
            if "media" in entry:
                p = Photo.from_json_structure(entry["media"])
                photos.append(p)

    return photos


def merge_conversation(directory: str) -> dict:
    """
    In `directory`, there are multiple JSON files, named like message_1.json,
    message_2.json, etc. They're split up for performance reasons, I assume.

    This function merges them and returns the resulting dictionary.
    """
    # Initialize a list to keep track of all json files in the directory
    json_files = [f for f in os.listdir(directory) if f.endswith(".json")]
    # FIXME: If the numbers exceed two digits, then the sorting will be wrong.
    #        Need to use something like natsort.
    #        https://pypi.org/project/natsort/
    json_files.sort()

    # Initialize an empty dict for the merged data
    merged_data = {}

    for index, file_name in enumerate(json_files):
        file_path = os.path.join(directory, file_name)
        with open(file_path, "r") as file:
            data = json.load(file)

            if index == 0:
                # For the first file, save all its contents
                merged_data = data
            else:
                # For subsequent files, only append the 'messages' list
                merged_data["messages"].extend(data["messages"])

    return merged_data


def extract_photos_from_messages(messages: list[dict]) -> list[Photo]:
    """
    This function accepts a list containing all of the messages from a
    conversation. The dictionary entries are not uniform. Some of them have a
    `photos` key, which contains a list of all photos attached to the message.

    This function returns a list of photos.
    """
    photos: list[Photo] = []
    for message in messages:
        if "photos" in message:
            for photo in message["photos"]:
                p = Photo.from_json_structure(photo)
                photos.append(p)

    return photos


def get_all_message_dirs() -> list[str]:
    directories = []
    for directory in (INBOX_DIR, ARCHIVED_DIR):
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entry.is_dir():
                    directories.append(entry.path)

    return directories


def modify_date_taken(photo_path: str, new_date: DateTime) -> None:
    """
    Modify the "date taken" field in the EXIF data of a photo.

    Does nothing if the photo doesn't have a .jpg extension.
    """

    if not photo_path.endswith(".jpg"):
        return

    # Load the EXIF data from the photo
    exif_dict = piexif.load(photo_path)

    # Convert the new date to the EXIF date format: "YYYY:MM:DD HH:MM:SS"
    formatted_date = new_date.strftime("%Y:%m:%d %H:%M:%S")

    # Modify the DateTimeOriginal field
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = formatted_date

    # Convert EXIF data back to binary
    exif_bytes = piexif.dump(exif_dict)

    # Write the modified EXIF data back to the photo
    piexif.insert(exif_bytes, photo_path)


def read_json(filename: str) -> Any:
    with open(filename, "r") as file:
        return json.load(file)


def main() -> None:
    # First, go through all the conversations and collect all of the photos.
    message_dirs = get_all_message_dirs()
    all_message_photos: list[Photo] = []
    for message_dir in message_dirs:
        conversation = merge_conversation(message_dir)
        message_photos = extract_photos_from_messages(conversation["messages"])
        all_message_photos.extend(message_photos)

    # Then we can get the photos from the albums.
    album_photos = get_photos_from_album(ALBUM_DIR)

    # Then, we get the uncategorized photos, which are in the same format as
    # the albums.
    uncategorized = read_json(UNCATEGORIZED_PHOTOS)
    uncategorized = uncategorized["other_photos_v2"]
    uncategorized_photos = extract_photos_from_list(uncategorized)

    # Lastly, we get all the photos from posts.
    posts = read_json(POSTS_AND_CHECKINS)
    posts_photos = extract_photos_from_posts(posts)

    # Now we merge them into one.
    all_photos = all_message_photos + album_photos + uncategorized_photos + posts_photos

    # Finally, before editing the EXIF data, we append the URI root so the paths
    # are correct, and convert the timestamp into a datetime object.
    for photo in all_photos:
        filepath = URI_ROOT + photo.uri
        timestamp = datetime.datetime.fromtimestamp(photo.timestamp, datetime.UTC)
        modify_date_taken(filepath, timestamp)


if __name__ == "__main__":
    main()
