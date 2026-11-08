# Titleblocks
A page SVG, usually with your name or company logo, that makes your drawings look professional.

## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")       |-- yourpn/
                                           |-- earlier revs/
fileio.path("revision history")            |-- revhistory.csv
fileio.dirpath("rev_directory")            L-- your rev/
fileio.path("params")                          |-- params.json
fileio.path("drawing")                         |-- drawing.svg
fileio.path("attributes")                      |-- attributes.json
fileio.path("gitignore")                       L-- .gitignore
```

A build writes `.gitignore` in the revision folder. This project type ignores:

- `*.tmp`

Rules already in the file stay.
