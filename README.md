Terrible name for this project, has nothing to do with scraping.

I have a bunch of data that I got from facebook, and this repository is going to be the home of various scripts to clean, categorize, and analyze the data.

So far, all I have is the `edit_photo_exif.py` script, which will edit the EXIF data of photos to have dates that match when they were posted, so I can upload to google images and they'll be in the right spot. In some cases the original exif data was actually saved, just not in the photos themselves. Which makes sense from a privacy standpoint.

If you want to use this, just plop your extracted facebook data into the facebook_data directory.
