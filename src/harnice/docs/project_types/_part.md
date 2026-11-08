# Parts
Buyable or buildable child item that goes into a harness.


## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")       |-- yourpn/
                                           |-- earlier revs/
fileio.path("revision history")            |-- revhistory.csv
fileio.dirpath("rev_directory")            L-- your rev/
fileio.path("drawing")                         |-- drawing.svg
fileio.path("drawing png")                     |-- drawing.png
fileio.path("attributes")                      |-- attributes.json
fileio.path("model")                           |-- model.step
fileio.path("gitignore")                       L-- .gitignore
```

A build writes `.gitignore` in the revision folder. This project type ignores:

- `*.tmp`

Rules already in the file stay.
